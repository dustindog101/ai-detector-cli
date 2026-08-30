# fish completion for ai-detect

complete -c ai-detect -f

complete -c ai-detect -l compare -s c -d 'Compare original vs modified documents' -r -F
complete -c ai-detect -l batch -s b -d 'Batch-scan a directory' -r -a '(__fish_complete_directories)'
complete -c ai-detect -l recursive -s r -d 'Recurse into subdirectories with --batch'
complete -c ai-detect -l glob -d 'Only files matching this glob' -r
complete -c ai-detect -l live-only -d 'Run only live HTTP cloud detectors'
complete -c ai-detect -l local-only -d 'Run only local statistical engines'
complete -c ai-detect -l browser -d 'Include browser automation engines'
complete -c ai-detect -l all -d 'Run every engine'
complete -c ai-detect -l engines -d 'Comma-separated engine keys' -r -a 'zerogpt sapling gltr burstiness perplexity lexicon gptzero copyleaks quillbot scribbr writer contentdetector isgen gptzero-api winston originality pangram detecting-ai binoculars grammarly zerogptcom'
complete -c ai-detect -l list-engines -d 'List registered engines'
complete -c ai-detect -l workers -s w -d 'Max concurrent workers' -r
complete -c ai-detect -l timeout -d 'Global HTTP timeout seconds' -r
complete -c ai-detect -l verbose -s v -d 'Verbose diagnostics'
complete -c ai-detect -l json -d 'Output JSON'
complete -c ai-detect -l export -s e -d 'Export report file' -r -F
complete -c ai-detect -l no-sentences -d 'Hide sentence breakdown'
complete -c ai-detect -l threshold -s t -d 'Max AI percent for exit 0' -r
complete -c ai-detect -l stdin -d 'Read from stdin'

complete -c ai-detect -F -a '(__fish_complete_suffixes .txt .md .markdown .rtf .json .csv .html .htm .docx .pdf)'
