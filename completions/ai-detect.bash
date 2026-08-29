# bash completion for ai-detect
_ai_detect_completions() {
    local cur prev
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    local flags="--compare --batch --recursive --glob --live-only --local-only --browser --all
        --engines --list-engines --workers --timeout --verbose --json --export
        --no-sentences --threshold --stdin --help"

    case "${prev}" in
        --threshold|-t|--workers|-w|--timeout)
            COMPREPLY=() ;;
        --export|-e)
            COMPREPLY=( $(compgen -f -- "${cur}") ) ;;
        --batch|-b|--glob)
            COMPREPLY=( $(compgen -d -- "${cur}") $(compgen -f -X '!*.@(txt|md|markdown|rtf|json|csv|html|htm|docx|pdf)' -- "${cur}") ) ;;
        --compare|-c)
            COMPREPLY=( $(compgen -f -- "${cur}") ) ;;
        --engines)
            local engines="zerogpt sapling gltr burstiness perplexity lexicon gptzero copyleaks quillbot scribbr writer contentdetector isgen"
            COMPREPLY=( $(compgen -W "${engines}" -- "${cur}") ) ;;
        *)
            COMPREPLY=( $(compgen -W "${flags}" -- "${cur}") $(compgen -f -X '!*.@(txt|md|markdown|rtf|json|csv|html|htm|docx|pdf)' -- "${cur}") ) ;;
    esac
    return 0
}
complete -F _ai_detect_completions ai-detect
