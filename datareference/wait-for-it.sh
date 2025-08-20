#!/bin/bash
# Wait for a PostgreSQL service to become available
# Usage: wait-for-it.sh host:port [-t timeout] [-- command args]

cmdname=$(basename $0)
TIMEOUT=300  # Augmentation du timeout par défaut à 300 secondes
QUIET=0
STRICT=0
CHILD=0
PROTOCOL="tcp"
IS_POSTGRES=1  # Considérer par défaut que c'est PostgreSQL

usage() {
    cat << USAGE >&2
Usage:
    $cmdname host:port [-t timeout] [-- command args]
    -t TIMEOUT                      Timeout in seconds, zero for no timeout
    -- COMMAND ARGS                 Execute command with args after the test finishes
USAGE
    exit 1
}

wait_for_postgres() {
    if [[ $TIMEOUT -gt 0 ]]; then
        echo "⏳ Waiting $TIMEOUT seconds for PostgreSQL at $HOST:$PORT..."
    else
        echo "⏳ Waiting for PostgreSQL at $HOST:$PORT without a timeout"
    fi
    
    start_ts=$(date +%s)
    while :
    do
        echo "  > Checking PostgreSQL connection to $HOST:$PORT ($(date))..."
        
        # Utiliser pg_isready qui est plus approprié pour PostgreSQL
        PGPASSWORD=${PGPASSWORD:-postgres} pg_isready -h $HOST -p $PORT -U ${PGUSER:-postgres} -d ${PGDATABASE:-postgres} > /dev/null 2>&1
        result=$?
        
        if [[ $result -eq 0 ]]; then
            end_ts=$(date +%s)
            echo "✅ PostgreSQL at $HOST:$PORT is available after $((end_ts - start_ts)) seconds"
            break
        elif [[ $result -eq 1 ]]; then
            echo "  > Server is rejecting connections. Checking PostgreSQL environment variables:"
            echo "  > PGHOST=${PGHOST}, PGPORT=${PGPORT}, PGUSER=${PGUSER}, PGDATABASE=${PGDATABASE}"
        elif [[ $result -eq 2 ]]; then
            echo "  > No response from server. Server might be starting up."
        elif [[ $result -eq 3 ]]; then
            echo "  > No attempt was made to connect to the server due to a missing parameter."
            echo "  > PGHOST=${PGHOST}, PGPORT=${PGPORT}, PGUSER=${PGUSER}, PGDATABASE=${PGDATABASE}"
        else
            echo "  > pg_isready returned unknown status: $result"
        fi
        
        sleep 5  # Intervalle de vérification de 5 secondes
        
        if [[ $TIMEOUT -gt 0 ]]; then
            curr_ts=$(date +%s)
            elapsed=$((curr_ts - start_ts))
            remaining=$((TIMEOUT - elapsed))
            
            if [[ $elapsed -gt $TIMEOUT ]]; then
                echo "❌ Timeout reached after ${elapsed}s. PostgreSQL at $HOST:$PORT is still not available"
                echo "  > Last pg_isready result: $result"
                echo "  > PGHOST=${PGHOST}, PGPORT=${PGPORT}, PGUSER=${PGUSER}, PGDATABASE=${PGDATABASE}"
                # Essayons une dernière vérification avec netcat pour voir si le port est ouvert
                nc -z $HOST $PORT > /dev/null 2>&1
                nc_result=$?
                if [[ $nc_result -eq 0 ]]; then
                    echo "  > TCP port is open but PostgreSQL is not accepting connections. Server might be starting up or configured incorrectly."
                else
                    echo "  > TCP port is closed. Server might not be running or is not accessible from this container."
                fi
                exit 1
            else
                echo "  > Still waiting for PostgreSQL at $HOST:$PORT... (${elapsed}s elapsed, ${remaining}s remaining)"
            fi
        fi
    done
    return $result
}

while [[ $# -gt 0 ]]
do
    case "$1" in
        *:* )
        hostport=(${1//:/ })
        HOST=${hostport[0]}
        PORT=${hostport[1]}
        shift 1
        ;;
        -t)
        TIMEOUT="$2"
        if [[ $TIMEOUT == "" ]]; then break; fi
        shift 2
        ;;
        --)
        shift
        CLI="$@"
        break
        ;;
        --help)
        usage
        ;;
        *)
        echo "Unknown argument: $1"
        usage
        ;;
    esac
done

if [[ "$HOST" == "" || "$PORT" == "" ]]; then
    echo "Error: you need to provide a host and port to test."
    usage
fi

echo "🔄 Starting PostgreSQL connection check to $HOST:$PORT with timeout=${TIMEOUT}s"
echo "  > Using environment: PGUSER=${PGUSER}, PGPASSWORD=${PGPASSWORD}, PGDATABASE=${PGDATABASE}"
wait_for_postgres
RESULT=$?

if [[ $CLI != "" ]]; then
    if [[ $RESULT -ne 0 ]]; then
        exit $RESULT
    fi
    echo "▶️ Executing command: $CLI"
    exec $CLI
else
    exit $RESULT
fi 