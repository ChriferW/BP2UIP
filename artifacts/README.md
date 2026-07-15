# Artifacts

Pipeline outputs, committed so a visitor can inspect every intermediate
without running anything.

Layout, once the pipeline produces output (nothing is generated yet):

```
artifacts/
├── estate/estate.json            whole-estate model from bp2uip parse
└── <process-slug>/               one directory per process
    ├── manifest.json             index of this process's artifacts
    ├── intent-spec.json          the IR, draft or approved
    ├── provenance.jsonl          append-only event log, hash-chained
    ├── uplift.json               agentic-uplift findings
    ├── pdd.md / pdd.docx         as-is process document
    ├── sdd.md / sdd.docx         to-be design document
    └── emitted/                  generated .xaml, BPMN, manifests
```

Committed artifacts are never hand-edited. Corrections are new
provenance events; changes come from rerunning the pipeline.
