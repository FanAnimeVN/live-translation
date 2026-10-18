# llama.cpp structured output: pinned runtime findings

Checked: **2026-10-13**. Scope: the local `/v1/chat/completions` integration and first-party llama.cpp documentation/source. The main task supplied the installed binary version: **0.6.0-dev, build 11429, commit `d81235049`, Clang 20.1.8, Windows x86_64**. GitHub resolves that commit to **`d81235049384534c167caea52b85a694f6103d14`**; every external source below is pinned to it. The provisioner selects `b11429`. [Pinned source](https://github.com/ggml-org/llama.cpp/tree/d81235049384534c167caea52b85a694f6103d14), [local provisioner](../scripts/provision_llama.py)

This researcher read source only: no inference, model download, cloud translation, private dataset or API-key access. The separate binary probe reported by the main task is identified below. No production code was changed.

## 1. The existing nested request is accepted

`LlamaWorker.generate` already sends the recognized shape:

```json
{
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "translation",
      "schema": {
        "type": "object",
        "properties": {"r000": {"type": "string"}},
        "required": ["r000"],
        "additionalProperties": false
      }
    }
  }
}
```

The parser reads `response_format.json_schema.schema`. Wrapper metadata such as `name` and `strict` is not read by this branch. **Changing the API shape is not supported as a fix for the reported failure.** [Pinned request parser, lines 1204–1227](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tools/server/server-common.cpp#L1204), [current request](../companion/manga_live/providers.py)

Here `S` means an actual schema object, and `G` a GBNF string:

| Request field | Pinned behavior |
| --- | --- |
| `response_format: {type:"json_schema", json_schema:{schema:S}}` | Uses `S`; current application form. |
| `response_format: {type:"json_object", schema:S}` | Uses `S`. |
| `response_format: {type:"json_object"}` | Selects generic object output. |
| `response_format: {type:"json_schema", schema:S}` | **Does not read `S`**; absent nested schema becomes generic object output. |
| `json_schema:S` at request top level | Accepted extension. |
| `grammar:G` at request top level | Accepted extension. |
| `response_format: {type:"text"}` | Adds no JSON constraint itself. |

The response-format rows follow the chat parser. The top-level extensions are also documented and handled by the completion parameter parser. [Chat parser](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tools/server/server-common.cpp#L1209), [completion parameter handler](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tools/server/server-schema.cpp#L216), [grammar API documentation](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/grammars/README.md#L113)

**Documentation discrepancy:** the pinned server README includes the flat `type:"json_schema", schema:S` example. Its grammar README and actual parser use the nested wrapper. Use the parser for this binary. [Server README](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tools/server/README.md#post-v1chatcompletions-openai-compatible-chat-completions-api)

## 2. Rejection is not universal schema validation

- An unknown, nonempty string `response_format.type` raises `invalid_argument`; the HTTP wrapper maps this to **400**. The error text omits `json_schema` even though the branch accepts it. [Request parser](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tools/server/server-common.cpp#L1217), [HTTP exception mapping](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tools/server/server.cpp#L48)
- A non-null top-level `json_schema` together with a nonempty top-level `grammar` raises `runtime_error` in the chat parser; that exception maps to **500**. Do not combine constraint forms. [Conflict check](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tools/server/server-common.cpp#L1204), [exception mapping](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tools/server/server.cpp#L64)
- Missing nested schema silently weakens to object output. Some wrong parameter types also fall back to defaults with a warning. A successful HTTP response alone does not prove the requested constraint was applied. [Parameter fallback](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tools/server/server-common.h#L37)
- A grammar that fails sampler initialization produces **400**. JSON-schema support is a subset; unsupported schema features are not uniformly rejected. [Sampler initialization](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tools/server/server-context.cpp#L1761), [documented limitations](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/grammars/README.md#L175)

These are source-derived outcomes, not a binary test matrix of malformed requests.

## 3. Grammar constrains prefixes; strings can still contain commentary

With `--jinja`, the parsed schema enters the template generation parameters. The generic automatic parser builds a schema-constrained response grammar with `grammar_lazy=false`; sampling rejects tokens outside the active grammar. Its response parser can also accept fenced JSON and reasoning wrappers, then extract message content. This is not an unconditional promise that every raw generation consists solely of JSON. [Template path](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/common/chat.cpp#L1209), [automatic parser and grammar](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/common/chat-auto-parser-generator.cpp#L59), [grammar rejection sampling](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/common/sampling.cpp#L599)

The current `compact_schema` requires exact keys and string values, with **no string length or content restriction**. Ordinary Unicode, braces and prose are legal inside a JSON string. A curly closing quotation mark (`”`, U+201D) is ordinary string content; only an unescaped ASCII quotation mark (`"`, U+0022) closes that value. The converter's unconstrained string rule allows repeated characters without a finite bound. [Current schema](../companion/manga_live/prompts.py), [pinned string grammar](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/common/json-schema-to-grammar.cpp#L221)

**Interpretation of the reported failure:** the main task inspected its authored offline output and reported that the `r003` value never received a closing ASCII quote. The subsequent brace and repeated Chinese instruction can therefore remain **inside that unfinished string**, consistent with an allowed grammar prefix. Their visual appearance after a curly quote does not establish a constraint bypass. This researcher did not inspect private data or independently validate the entire generated token sequence.

`minLength`/`maxLength` can bound strings in this pinned converter. They can limit runaway values; they cannot establish Vietnamese language, translation meaning or freedom from commentary. Any new bound needs a justified policy and regression checks for legitimate long dialogue. [Bounded string conversion](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/common/json-schema-to-grammar.cpp#L880)

## 4. Token limits can interrupt a legal prefix

The server ends generation when the prediction budget runs out, without waiting for a string/object to close. The chat response maps this to `finish_reason:"length"`. A stop sequence or other stopping condition also does not prove schema completion. Keep the existing truncation rejection and JSON parsing. [Budget stop](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tools/server/server-context.cpp#L1864), [finish reason and content fallback](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tools/server/server-task.cpp#L393), [local truncation check](../companion/manga_live/providers.py), [local JSON parser](../companion/manga_live/validation.py)

The main task separately reported a local probe through the same production `LlamaWorker.generate`: schema `{probe: string enum["OK"]}` plus an unrelated translation instruction returned exactly `{"probe":"OK"}`. This supports recognition and enforcement of the current request format on the installed binary. It does **not** establish translation quality, completion under arbitrary budgets or enforcement of every schema keyword. This researcher did not run that probe.

## 5. Application checks remain necessary

Keep three checks separate:

1. **Completion and syntax:** reject `finish_reason:"length"`; parse the returned content completely as JSON after the application's explicit wrapper handling. Do not repair an unfinished string by guessing its ending.
2. **Structure:** verify the exact expected IDs, count, value types, nonempty translations and application text-size limits. A schema-conversion subset or provider change must not allow output to attach to the wrong bubble.
3. **Content and meaning:** detect unusable source echo/commentary and preserve locked terminology, directed pronouns, ambiguity, negation and utterance roles. String syntax does not check these properties. Narrow automatic guards are not a semantic quality score.

The application already has truncation, parsing, ID/type and some output/terminology/address checks. Inspect their actual coverage and test new observed failure patterns separately; do not infer a language guarantee from JSON success. [Provider flow](../companion/manga_live/providers.py), [validation](../companion/manga_live/validation.py), [terminology](../companion/manga_live/terminology.py), [address checks](../companion/manga_live/linguistics.py)

**Version limit:** these findings concern the supplied b11429 binary and pinned source. Build features, template selection and later llama.cpp revisions can change grammar/parser behavior. The binary probe provides limited local corroboration; source inspection does not replace end-to-end regression checks.
