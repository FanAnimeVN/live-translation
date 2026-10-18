# Local JSON Schema constraints — primary-source check, 2026-10-15

The installed `runtime/llama/llama-server.exe --version` returned **0.6.0-dev, build 11429, commit `d81235049`, Clang 20.1.8, Windows x86_64** (exit 0). Sources below are pinned to the matching full commit, `d81235049384534c167caea52b85a694f6103d14`. This check loaded no model, ran no inference, accessed no private dataset or keys, and changed no production code or configuration.

## Supported request and constraints

The chat parser reads the existing nested form:

```json
{"response_format":{"type":"json_schema","json_schema":{"name":"translation","schema":{"type":"object","properties":{"r000":{"type":"string"}},"required":["r000"],"additionalProperties":false}}}}
```

`name`/`strict` do not control this parser branch. A missing nested `schema` becomes generic object output, so HTTP success alone does not establish enforcement. [Pinned request parser](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tools/server/server-common.cpp#L1204-L1227).

| Feature | Pinned behavior and evidence |
| --- | --- |
| `additionalProperties:false` | Enforces declared keys; use `required` for mandatory keys. Upstream integration tests reject extra keys and missing required keys. [Integration tests](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tests/test-grammar-integration.cpp#L1294-L1349). |
| `maxLength`, without a pattern/format | Supported; tests accept bounded strings and reject longer strings. This is a character constraint, not a token budget. [Length tests](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tests/test-grammar-integration.cpp#L990-L1030). |
| Anchored negated Unicode class | Technically supported: GBNF supports Unicode code points, negated classes and `{m,n}`; the converter copies classes into the grammar. [GBNF definitions](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/grammars/README.md#L34-L56), [class conversion](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/common/json-schema-to-grammar.cpp#L463-L484). |

## Material caveats

- A nonempty `pattern` returns **before** `minLength`/`maxLength` handling. Those keywords do not compose here: encode the bound as `{1,N}` inside the pattern. [String dispatch](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/common/json-schema-to-grammar.cpp#L880-L897).
- Patterns must start with `^` and end with `$`. Unsupported constructs can degrade to an unrestricted string with a warning; unanchored patterns, shorthand `\w`, and lookahead have explicit fallback tests. Invalid patterns can error. [Fallback tests](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tests/test-json-schema-to-grammar.cpp#L1370-L1452).
- Pattern conversion wraps a rule in quotes; it does **not** automatically intersect it with the normal JSON string character rule. A bare `^[^”]{1,N}$` can admit unescaped ASCII quotes, backslashes and controls. Escape branches need separate care: permitting arbitrary `\uXXXX` sequences can encode a banned quote. [Wrapper and normal character rule](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/common/json-schema-to-grammar.cpp#L231-L232), [pattern wrapper](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/common/json-schema-to-grammar.cpp#L588-L594). Upstream's quote-pattern fixture itself emits three unescaped quote characters. [Fixture](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tests/test-json-schema-to-grammar.cpp#L718-L729).
- These findings concern the built-in GBNF converter. There is also an optional LLGuidance dispatch; version output alone does not certify build flags or active template/parser. [Dispatch](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/common/json-schema-to-grammar.cpp#L937-L955). The generic automatic chat parser builds a non-lazy grammar for response schemas. [Automatic parser](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/common/chat-auto-parser-generator.cpp#L64-L72).

## Viability for the reported closing-quote loop

**Source-derived conclusion:** a per-value bounded class can prohibit selected closing-quote code points during generation without changing captured source text. For example, this *regex value before JSON encoding* excludes U+201D, JSON-unsafe characters and all escape sequences:

```text
^[^"\\\u0000-\u001F\u007F”]{1,240}$
```

This is an illustrative design, **not a tested schema or recommended length policy**. It also disallows legitimate ASCII dialogue quotes, backslashes and line breaks; therefore it is unsuitable as a universal translation constraint. A production candidate must preserve necessary escaped content or decline to constrain that value.

Selection of forbidden characters is a separate application decision. Absence of a closing quote in one crop is insufficient evidence: quotes can span bubbles, OCR can miss punctuation, and a reader may confirm an exception. Keep source evidence unchanged, apply only evidence-backed per-ID restrictions, and retain review/bounded repair for uncertain or rejected values. These are repository acceptance requirements, not guarantees provided by llama.cpp.

A smart closing quote is ordinary JSON string content; banning it does not make it an ASCII JSON delimiter or prove that the model will finish sooner. The model can still emit irrelevant text within the permitted language. The schema is not injected into the prompt, and grammar sampling has performance caveats. [Grammar guide](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/grammars/README.md#L105-L128). Keep complete JSON parsing, exact ID/type/content checks and truncation rejection: the server can return `finish_reason:"length"`. [Chat finish reason](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tools/server/server-task.cpp#L393-L409).

No candidate was exercised against the installed binary or Hy-MT2 here. Constrained syntax is **not translation correctness**, and this research establishes neither real-manga quality nor latency improvements. Preserve the private ground-truth gate before changing defaults or packaging.

## Follow-up: preserve ordinary JSON escapes

The pinned converter supports `(?:...)`, ordinary groups, alternatives and repetition. Upstream fixtures explicitly cover noncapturing groups with alternatives and nested noncapturing groups; no capturing-group workaround is needed. [Group fixtures](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tests/test-json-schema-to-grammar.cpp#L1346-L1368).

A source-compatible candidate regex value is:

```text
^(?:[^"\\\u0000-\u001F”]|\\["\\/bfnrt]){1,240}$
```

Equivalently, construct that value in Python with a raw string, then serialize the schema normally:

```python
pattern = r'^(?:[^"\\\u0000-\u001F”]|\\["\\/bfnrt]){1,240}$'
```

The second alternative permits only JSON's short escapes: escaped ASCII quote, backslash, slash, backspace, form feed, newline, carriage return and tab. It omits `u`, so arbitrary Unicode escapes cannot encode the banned U+201D. Each group repetition consumes one direct character or one short escape. `{1,240}` is illustrative; `*` would restore an unbounded, possibly empty string. [Converter group/class/alternative handling](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/common/json-schema-to-grammar.cpp#L439-L545).

This candidate targets the converter's serialized JSON grammar. It is not equivalent to applying that regex to the decoded translation: decoded ASCII quotes/newlines would fail the direct-character branch. Do not reuse it unchanged for a separate decoded-value validator; retain independent content checks.

Keep the six-character spellings `\u0000` and `\u001F` **in the pattern value**. Do not substitute actual NUL/control bytes: grammar parsing uses a null-terminated `const char *`, and NUL inside a class causes unexpected end of input. GBNF interprets these textual Unicode escapes itself. [Character parsing](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/src/llama-grammar.cpp#L147-L168), [class parsing](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/src/llama-grammar.cpp#L511-L539).

The parser's repetition threshold is 2000. A maximum above it becomes unbounded; a minimum above it, or excessive repeated rule complexity, errors. Validate the generated grammar for the chosen bound. [Threshold and checks](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/src/llama-grammar.cpp#L11), [complexity check](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/src/llama-grammar.cpp#L436-L466), [bound handling](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/src/llama-grammar.cpp#L615-L621).

This follow-up is source inspection, not execution of this candidate through the installed converter/server. The source-evidence and semantic-quality limitations above still apply.
