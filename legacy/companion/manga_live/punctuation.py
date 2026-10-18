"""Source-aware formatting checks. Never rewrite dialogue or OCR evidence.

JSON delimiters are not speech. But source quotation, partial quotation across
bubbles, ellipses and stutters can carry meaning; a global quote-strip is unsafe.
These checks ask for the existing bounded repair, not a semantic quality score.
"""
import re

QUOTE_PAIRS=(("「","」"),("『","』"),("“","”"),("«","»"),("\"","\""),("＂","＂"))
QUOTE_MARKS="".join(left+right for left,right in QUOTE_PAIRS)


def quote_imbalanced(value):
    return any(value.count(left)%2 if left==right else value.count(left)!=value.count(right)
               for left,right in QUOTE_PAIRS)


def outer_quotation(value):
    return any(len(value)>=2 and value.startswith(left) and value.endswith(right)
               for left,right in QUOTE_PAIRS)


def output_punctuation_issues(source,target,protected_values=()):
    """Return narrow reasons; preserve values verbatim even when flagged.

    Reader-locked names may intentionally contain quotes. Source-present paths
    and literal escapes are data too. A quote in a middle clause is not mistaken
    for an extra whole-bubble quotation wrapper.
    """
    issues=[]
    target=target.strip()
    protected_exact=any(target.casefold()==value.casefold() for value in protected_values)
    framed=target.rstrip(",;，； \t\r\n")
    has_source_quotes=any(mark in source for mark in QUOTE_MARKS)
    if not protected_exact:
        if outer_quotation(framed):
            if not has_source_quotes:issues.append("added_outer_quotes")
            elif quote_imbalanced(source):issues.append("unsupported_quote_completion")
        elif not has_source_quotes and framed and (framed[0] in QUOTE_MARKS or framed[-1] in QUOTE_MARKS):
            issues.append("orphan_output_quote")
        # A closing quote followed by a dangling separator is a common leaked
        # JSON-list suffix. Do not flag an actual source quote followed by a comma.
        closes=re.escape("".join(right for _,right in QUOTE_PAIRS))
        if re.search(r"["+closes+r"]\s*[,;，；]\s*$",target) and not re.search(r"["+closes+r"]\s*[,;，；、]\s*$",source):
            issues.append("trailing_serialization_punctuation")
        if "\\" not in source and re.search(r'\\+(?:["nrt]|u[0-9a-fA-F]{4})',target):
            issues.append("literal_serialization_escape")
        if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]",target) and not re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]",source):
            issues.append("unsupported_control_character")
    return issues
