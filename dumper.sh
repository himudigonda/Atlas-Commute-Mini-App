#!/bin/bash
set -euo pipefail
dump_content() {
    local total_lines=0
    local total_words=0
    local total_chars=0

    echo "🌳 Project Structure:"
    if command -v tree >/dev/null 2>&1; then
        tree -L 3 -I '.*|__pycache__|venv'
    else
        find . -maxdepth 3 -not -path '*/.*' -not -name "." -not -path "*__pycache__*" -not -path "*venv*" | sort | sed -e 's/[^/]*\//|  /g' -e 's/|  \([^|]\)/└── \1/'
    fi
    
    while read -r file; do
        if file --mime "$file" | grep -q 'charset=binary'; then continue; fi
        
        echo "======================================================================================="
        echo "FILE: $file"
        echo "======================================================================================="
        cat "$file"
        echo -e "\n"
        
        # Accumulate stats
        stats=($(wc "$file"))
        total_lines=$((total_lines + stats[0]))
        total_words=$((total_words + stats[1]))
        total_chars=$((total_chars + stats[2]))
    done < <(find . -type f -not -path '*/.*' -not -path '*/venv/*' -not -name 'uv.lock')

    echo "======================================================================================="
    echo "📊 FINAL DUMP STATS:"
    echo "Total Lines: $total_lines"
    echo "Total Words: $total_words"
    echo "Total Chars: $total_chars"
    echo "======================================================================================="
}
dump_content
