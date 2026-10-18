param([Parameter(Mandatory=$true)][string]$InputDocx,[Parameter(Mandatory=$true)][string]$OutputPdf)
# File conversion API only. Own hidden Word instance, no personal documents/UI.
$inputFile=[System.IO.Path]::GetFullPath($InputDocx)
$outputFile=[System.IO.Path]::GetFullPath($OutputPdf)
if (-not [System.IO.File]::Exists($inputFile)) { throw 'Report does not exist' }
$word=$null
$document=$null
try {
    $word=New-Object -ComObject Word.Application
    $word.Visible=$false
    $word.DisplayAlerts=0
    $document=$word.Documents.Open($inputFile,$false,$true)
    $document.Repaginate()
    $document.ExportAsFixedFormat($outputFile,17)
} finally {
    if ($null -ne $document) { $document.Close(0); [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($document) }
    if ($null -ne $word) { $word.Quit(0); [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) }
}
if (-not [System.IO.File]::Exists($outputFile)) { throw 'Word did not export PDF' }
