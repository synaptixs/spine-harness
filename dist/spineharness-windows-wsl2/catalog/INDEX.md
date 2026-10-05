# Expanded reference scenarios

30 additional tasks: 15 edits and 15 new modules. Each runs independently from the same pinned baseline. They cover different requirements in the reference repository, not 30 independent repositories or actual Jira issues.

| ID | Kind | Area | Requirement | Judge cases |
|---|---|---|---|---:|
| EXT-REACH-1 | edit | Traversal | Reachable call targets | 4 |
| EXT-PATH-1 | edit | Traversal | Lexicographic shortest call path | 5 |
| EXT-IMPACT-1 | edit | Traversal | Bounded reverse call impact | 5 |
| EXT-COMPONENTS-1 | edit | Traversal | Weak call components with isolates | 3 |
| EXT-LAYERS-1 | edit | Dependencies | Topological import layers | 5 |
| EXT-SCC-1 | create | Traversal | Strongly connected call groups | 3 |
| EXT-DANGLING-1 | create | Integrity | Dangling relation diagnostics | 3 |
| EXT-BALANCE-1 | create | Statistics | Unique call degree balance | 3 |
| EXT-LANGUAGE-1 | create | Integration | Cross-language call boundaries | 3 |
| EXT-LEAVES-1 | create | Traversal | Containment leaves under a root | 4 |
| EXT-DUPCOL-1 | edit | Schema | Duplicate database column diagnostics | 3 |
| EXT-FKCHECK-1 | edit | Schema | Foreign-key integrity diagnostics | 3 |
| EXT-DBORDER-1 | edit | Schema | Database insertion layers | 3 |
| EXT-SCHEMADIFF-1 | edit | Schema | Column-level schema drift | 3 |
| EXT-REQUIRED-1 | edit | Schema | Required database fields | 3 |
| EXT-RANGES-1 | create | Provenance | Merge adjacent provenance ranges | 4 |
| EXT-FILECOVER-1 | create | Provenance | Grounded symbol counts by repository/file | 3 |
| EXT-LOCATE-1 | create | Provenance | Find symbols at a source line | 4 |
| EXT-AMBIGUOUS-1 | create | Identity | Ambiguous internal symbol names | 3 |
| EXT-TOUCHED-1 | create | Provenance | Map changed lines to grounded symbols | 4 |
| EXT-MEDIAN-1 | edit | Statistics | Lower median call count | 4 |
| EXT-SHARE-1 | edit | Statistics | Top-k call concentration | 6 |
| EXT-MERGEFREQ-1 | edit | Statistics | Merge frequency snapshots by identity | 5 |
| EXT-RANK-1 | edit | Statistics | Dense ranks for called functions | 3 |
| EXT-ALLOCATE-1 | edit | Statistics | Proportional integer call-budget allocation | 6 |
| EXT-HANDLERS-1 | create | Coverage | Endpoint-to-handler coverage | 3 |
| EXT-ORPHANDOC-1 | create | Coverage | Unbound documentation pages | 3 |
| EXT-INTENTS-1 | create | Coverage | Untraced internal symbols | 3 |
| EXT-CUT-1 | create | Dependencies | Outgoing dependency boundary | 3 |
| EXT-OWNERS-1 | create | Ownership | Nearest containing modules | 4 |
