# SQ8 AMX alignment probe

**Decision: retain the native layout.** This is an ignored, synthetic signed-I8 × U8 scorer diagnostic on one CPU; it does not measure HTTP retrieval, recall, cluster RPS, or physical-memory bandwidth.

Source `3613d96dbba4cd559dad8abc433ab12dc8e74bfd` (tree `76bc738e8ecd97d97025d98acfb9ef84b90da5c8`); quantization focused tests passed (131 cases). The benchmark is test-only; no production engine source changed. Test binary SHA-256 `c21939cadde1f286b451d91f591a056fa1c88b4b9ce44cce090f5f1ce397f154`; build receipt SHA-256 `20c60e764ea8f986146456982a862a658e8463dfc54c29307474f0c2a85d8785`.

The native input uses stride 516/code offset 4. The aligned representation uses stride 576/code offset 64, with the same four-byte F32 offset at row byte 60 (`code_ptr - 4`) and the same 512 code bytes. The prepacked arm excludes data preparation; the copy-plus-score arm copies the offset and codes for every 1024-vector chunk inside the timer.

Each row has one warmup and seven measured sweeps. All three full-score FNV-1a64 hashes match, and independent integer/F32 oracle samples passed for each chunk. AMX call telemetry increased for each representation before timing; `VX_PFH=9`, `VX_PF8=6`.

| Vectors | nq | Native median (ms) | Prepacked aligned (ms) | Native / prepacked | Copy + aligned (ms) | Native / copy+score | Hashes |
|---:|---:|---:|---:|---:|---:|---:|:---:|
| 100,000 | 32 | 3.135 | 3.751 | 0.836× | 5.020 | 0.624× | equal |
| 100,000 | 64 | 3.333 | 4.207 | 0.792× | 5.114 | 0.652× | equal |
| 100,000 | 70 | 4.907 | 5.548 | 0.884× | 6.459 | 0.760× | equal |
| 100,000 | 96 | 4.480 | 4.916 | 0.911× | 6.611 | 0.678× | equal |
| 1,000,000 | 32 | 32.812 | 33.402 | 0.982× | 46.092 | 0.712× | equal |
| 1,000,000 | 64 | 39.904 | 40.464 | 0.986× | 56.375 | 0.708× | equal |
| 1,000,000 | 70 | 54.172 | 53.584 | 1.011× | 68.608 | 0.790× | equal |
| 1,000,000 | 96 | 46.774 | 46.981 | 0.996× | 68.852 | 0.679× | equal |

<details>
<summary>Raw samples (nanoseconds, in runner output order)</summary>


- n=100000, nq=32: native `[3388440, 3134683, 3203146, 2883049, 2960399, 2763857, 3362690]`; prepacked aligned `[4083404, 4017954, 3846401, 3663119, 3632199, 3751404, 3671830]`; copy + aligned `[5019937, 4700484, 5063641, 4262816, 4452907, 5051529, 5030850]`; medians `3134683, 3751404, 5019937`; FNV-1a64 `d43737e00bc3479a` (equal across variants).
- n=100000, nq=64: native `[3425028, 3333315, 3307672, 3407191, 3312088, 3290098, 3401851]`; prepacked aligned `[4206881, 4231505, 4176273, 4266233, 4215614, 4195940, 4169788]`; copy + aligned `[5212002, 5159623, 5059908, 5337234, 5022079, 5113865, 5078332]`; medians `3333315, 4206881, 5113865`; FNV-1a64 `9b0e16741d55be0b` (equal across variants).
- n=100000, nq=70: native `[4940712, 4746344, 4696948, 5177790, 4942362, 4839281, 4906536]`; prepacked aligned `[5486693, 5576274, 5572372, 5726854, 5514325, 5485771, 5548337]`; copy + aligned `[6543941, 6325041, 6910991, 6880860, 6459315, 6344403, 6391196]`; medians `4906536, 5548337, 6459315`; FNV-1a64 `d4a8db111c98d543` (equal across variants).
- n=100000, nq=96: native `[4891170, 4479608, 4692826, 4296337, 4184655, 4184207, 4549346]`; prepacked aligned `[5319719, 5536263, 4833039, 4768972, 4915912, 4851385, 5007321]`; copy + aligned `[7632305, 7220780, 6610725, 6514416, 6282469, 6513774, 6681974]`; medians `4479608, 4915912, 6610725`; FNV-1a64 `4203ced3046341d9` (equal across variants).
- n=1000000, nq=32: native `[32116993, 32374912, 32812036, 32145893, 33217030, 33831631, 33104093]`; prepacked aligned `[35094215, 33238137, 33402205, 34075335, 33124553, 34349319, 33075809]`; copy + aligned `[45998530, 46591269, 46669098, 46450529, 45561959, 45701125, 46091779]`; medians `32812036, 33402205, 46091779`; FNV-1a64 `1c53c14619d69d53` (equal across variants).
- n=1000000, nq=64: native `[40521271, 39903949, 41658189, 39597492, 38985933, 40104683, 39314062]`; prepacked aligned `[40396477, 40183873, 41656669, 40538390, 40370824, 40919111, 40463580]`; copy + aligned `[57753542, 56006888, 59886324, 56280769, 56375431, 56544394, 56342346]`; medians `39903949, 40463580, 56375431`; FNV-1a64 `001d4160489c2595` (equal across variants).
- n=1000000, nq=70: native `[56375475, 54560290, 54636143, 54172370, 53349472, 53978158, 53376362]`; prepacked aligned `[53039071, 53584268, 53712964, 53998446, 53501597, 53702106, 52908505]`; copy + aligned `[68608304, 67776819, 69467576, 68089933, 69402486, 68526354, 70496090]`; medians `54172370, 53584268, 68608304`; FNV-1a64 `669cb730082fde64` (equal across variants).
- n=1000000, nq=96: native `[45664545, 48395254, 45848520, 48283704, 46127859, 48209415, 46774215]`; prepacked aligned `[46980892, 47030780, 46688476, 46817264, 48764916, 48324493, 46740672]`; copy + aligned `[69474834, 70302990, 68852381, 70515209, 68034484, 68527324, 68344937]`; medians `46774215, 46980892, 68852381`; FNV-1a64 `1564a0905e050f89` (equal across variants).

</details>

Prepacked alignment had no consistent median gain: it was slower in seven of eight rows, with a 1.1% edge at 1M vectors / nq=70. Copy plus scoring was slower in all eight rows, so copying does not amortize within one scan here. The two 1M-vector layouts remain resident together during the run and occupy 1.092 GB decimal before overhead. These measurements are screening evidence only; they do not establish a production benefit.

Machine-readable [JSON](sq8-alignment-probe-20261111.json) and [CSV](sq8-alignment-probe-20261111.csv) retain all measurements and provenance.
