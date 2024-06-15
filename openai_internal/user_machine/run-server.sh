#!/bin/bash
ulimit -n 1024
ulimit -v $PROCESS_MEMORY_LIMIT
cd $HOME/.openai_internal/ || exit
if [ -f /usr/lib/x86_64-linux-gnu/libjemalloc.so.2 ]; then
    JEMALLOC_PATH=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2
elif [ -f /usr/lib/aarch64-linux-gnu/libjemalloc.so.2 ]; then
    JEMALLOC_PATH=/usr/lib/aarch64-linux-gnu/libjemalloc.so.2
else
    echo "libjemalloc not found"
    exit 1
fi
if [ ! -z "$JEMALLOC_PATH" ]; then
    echo "Using jemalloc at $JEMALLOC_PATH"
    export PYTHONMALLOC=malloc
    export MALLOC_CONF="narenas:1,background_thread:true,lg_tcache_max:10,dirty_decay_ms:5000,muzzy_decay_ms:5000"
    export LD_PRELOAD="$JEMALLOC_PATH"
fi
export PYDEVD_DISABLE_FILE_VALIDATION=1
exec tini -- python3 -m uvicorn --host 0.0.0.0 --port 8080 user_machine.app:app