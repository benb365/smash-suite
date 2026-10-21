# 回放观测恢复盘点

## 结论

`cases.json` 有 16 个案例、36 条观测引用；其中 A2-01 与 A2-02 指向同一 tracknet 文件，去重后 35 个唯一文件。按清单 SHA256 核对原工作区 `outputs/` 的 110 个文件，并检查获准的外部 tracknet 路径；没有发现任何清单输入的同名或同 SHA 文件。原工作区 `modules/rally/.runtime/` 目录不存在。因此当前没有可恢复的、经清单 SHA 确认的来源映射。

指定检查的 `/Users/bytedance/workspace/test/meterials/outputs/realtime-input-20261005/offline/01-02-clip/tracknet-points.jsonl` 当前不存在。`outputs/media-restore.json` 记录的是视频输入恢复及其来源映射，不包含这些回放观测文件；不能据此恢复观测输入。

## 清单文件核对

以下 35 个唯一清单文件均缺失于清单路径；在限定候选范围内也没有同名或 SHA 匹配项。表中案例列用于表示共享文件的全部引用。

| 案例引用 | 清单相对路径 | 期望 SHA256 | 盘点 |
|---|---|---|---|
| A1-01.diagnostics | `modules/rally/.runtime/m1-a-tuning-20261016/A1-01/01-01-clip/flight-diagnostics.jsonl` | `d562ae7597e763ecef146ad6f2d4a83123f7085a77cc0a73aac6499db23203c6` | 未找到同名或 SHA 匹配候选 |
| A1-02.diagnostics | `modules/rally/.runtime/m1-a-tuning-20261016/A1-02/01-01-clip/flight-diagnostics.jsonl` | `354c2d9cfaddeba7b0cd44f976e6387a51644f2a3c9a3ffb392feaf441d66c6a` | 未找到同名或 SHA 匹配候选 |
| A1-03.diagnostics | `modules/rally/.runtime/m1-a-check-20261016/A1-03/01-01-clip/flight-diagnostics.jsonl` | `a44161f50fb0a9adeb77aa5218a1551c1f61033281260524833dfdab80ea7fc3` | 未找到同名或 SHA 匹配候选 |
| A1-04.diagnostics | `modules/rally/.runtime/m1-a-check-20261016/A1-04/01-01-clip/flight-diagnostics.jsonl` | `b31fa0d22c4a7306d23398645ab8a26240f52c729252819cdcc27d3d60c339e6` | 未找到同名或 SHA 匹配候选 |
| A2-01.diagnostics, A2-02.diagnostics | `/Users/bytedance/workspace/test/meterials/outputs/realtime-input-20261005/offline/01-02-clip/tracknet-points.jsonl` | `81be1f32da0c7d06ff34cea9b9c2fd354478eaf7ce1dc92387fd4fe3432da68d` | 未找到同名或 SHA 匹配候选 |
| C1-01.native | `modules/rally/.runtime/m1-cd-coordinate-20261017/inference/01-01-clip/shuttle-candidates.jsonl` | `a5e3e5ac1074d26e37c1150449f0f4eb1755eeadab33b9752b5ebd9bd38c556e` | 未找到同名或 SHA 匹配候选 |
| C1-01.shifted | `modules/rally/.runtime/c1-weak-tracks-20261017/full-phase1-C1-01/candidates.jsonl` | `f1a7d66f7aaec6f28ea00c722be317acb919bcef6cce1903277592f71923d929` | 未找到同名或 SHA 匹配候选 |
| C1-01.people | `modules/rally/.runtime/c2-current-algorithm-20261018/relaxed-selection/C1-01/players.jsonl` | `2a99e3f30c24c6a1f39498da42a9abc0bc577fa4049296cb94730c4a957353f2` | 未找到同名或 SHA 匹配候选 |
| C1-01.flights | `modules/rally/.runtime/c2-current-algorithm-20261018/relaxed-selection/C1-01/flights.json` | `c41661b630fbe27b24bb6971af4e3c8923f66e2cace77703dc8d3cdfda981083` | 未找到同名或 SHA 匹配候选 |
| C1-02.native | `modules/rally/.runtime/m1-cd-coordinate-20261017/inference/01-02-clip/shuttle-candidates.jsonl` | `e015ba6caacfadb1f16398dee15a37b40078b2bbbd8ec1599c9745d94db18dc0` | 未找到同名或 SHA 匹配候选 |
| C1-02.shifted | `modules/rally/.runtime/c1-weak-tracks-20261017/full-phase1-C1-02/candidates.jsonl` | `a6ed8198b9a06c19ad734e67cd182acde01f5ea4eedd8b71451187a6065c6249` | 未找到同名或 SHA 匹配候选 |
| C1-02.people | `modules/rally/.runtime/c2-current-algorithm-20261018/relaxed-selection/C1-02/players.jsonl` | `422d363219a5593e8832d1bcf3aead89f846e2e433fe2bbeba79189e2dbd3966` | 未找到同名或 SHA 匹配候选 |
| C1-02.flights | `modules/rally/.runtime/c2-current-algorithm-20261018/relaxed-selection/C1-02/flights.json` | `1b6a9eb684de92feb1a98a16155e5554b05e8bf7a53433726553ed50aee1c616` | 未找到同名或 SHA 匹配候选 |
| C1-03.native | `modules/rally/.runtime/m1-cd-coordinate-20261017/inference/01-03-clip/shuttle-candidates.jsonl` | `1b13abeb755ed3974e8a95314daf0327c2853d3f75c0fdac4e83e8db8edd3a45` | 未找到同名或 SHA 匹配候选 |
| C1-03.shifted | `modules/rally/.runtime/c1-weak-tracks-20261017/full-phase1-C1-03/candidates.jsonl` | `522e03079a1b65a748eb6d334ba757ba6dc766ae7318bf99ee13879f794a1af6` | 未找到同名或 SHA 匹配候选 |
| C1-03.people | `modules/rally/.runtime/c2-current-algorithm-20261018/relaxed-selection/C1-03/players.jsonl` | `d193e8dcd55c3c1fdeac913bcc903e980fc5e406dc6c98a94d53760648e9c6c9` | 未找到同名或 SHA 匹配候选 |
| C1-03.flights | `modules/rally/.runtime/c2-current-algorithm-20261018/relaxed-selection/C1-03/flights.json` | `598f78ee0bb921c25597978637346429adc792905db4eb0cb3d4e077e0e0d7bd` | 未找到同名或 SHA 匹配候选 |
| C1-04.native | `modules/rally/.runtime/m1-cd-coordinate-20261017/inference/01-04-clip/shuttle-candidates.jsonl` | `fec1821960fb5276149508099681dfe14e4fa683ca0cfa75301056f4fceead22` | 未找到同名或 SHA 匹配候选 |
| C1-04.shifted | `modules/rally/.runtime/c1-weak-tracks-20261017/full-phase1-C1-04/candidates.jsonl` | `f00636cb004de1c84c8c35551d2c9f803aed211356c47ff2fadcc2fcbce3ce9d` | 未找到同名或 SHA 匹配候选 |
| C1-04.people | `modules/rally/.runtime/c2-current-algorithm-20261018/relaxed-selection/C1-04/players.jsonl` | `eb27acc60e15c00585ee0712bcdf2f5916286d3d636ebf9453041d6602b631d7` | 未找到同名或 SHA 匹配候选 |
| C1-04.flights | `modules/rally/.runtime/c2-current-algorithm-20261018/relaxed-selection/C1-04/flights.json` | `027bab9adb96579691744d102afd6059ff02910b1751630fbe883f100ff141c7` | 未找到同名或 SHA 匹配候选 |
| C2.native | `modules/rally/.runtime/c2-current-algorithm-20261018/observations/native.jsonl` | `0df835729f95628c49889bf22f188c6f46f224542d2c4d970d2f0e59fa849e30` | 未找到同名或 SHA 匹配候选 |
| C2.shifted | `modules/rally/.runtime/c2-current-algorithm-20261018/observations/shifted.jsonl` | `f409da29b754fe04caa07876a5111662ac8bb20036ce06e65e707c0b25b20aaf` | 未找到同名或 SHA 匹配候选 |
| C2.people | `modules/rally/.runtime/c2-current-algorithm-20261018/relaxed-selection/C2/players.jsonl` | `2c9232f3266278abb830e039cc9a5b3c89da17e2f190b7c9457eba9959f552e2` | 未找到同名或 SHA 匹配候选 |
| C2.flights | `modules/rally/.runtime/c2-current-algorithm-20261018/relaxed-selection/C2/flights.json` | `fbf5ab07b140da9c4e7aec0e1fe90af3f5cba332b55ab136ec2d153db9d57a1e` | 未找到同名或 SHA 匹配候选 |
| D1-01.signals | `modules/rally/.runtime/d1-person-motion-20261017/pose-local-flow-dense-01/D1-01-signals.npz` | `5a38545b962c925b413d5bcae5e496878cf6590969ee23f2c312ca765b8e9347` | 未找到同名或 SHA 匹配候选 |
| D1-01.people | `modules/rally/.runtime/d1-person-motion-20261017/D1-01/players-v2.jsonl` | `45259e7147dc6104dc044143aecfb6582da571efb07afa813888bb989ef21fe3` | 未找到同名或 SHA 匹配候选 |
| D1-02.signals | `modules/rally/.runtime/d1-person-motion-20261017/pose-local-flow-dense-01/D1-02-signals.npz` | `1c061345cb8805f873d38db5691bf3f332b7fe25c80c6ca86105c61c3fe65159` | 未找到同名或 SHA 匹配候选 |
| D1-02.people | `modules/rally/.runtime/d1-person-motion-20261017/D1-02/players-v2.jsonl` | `7f69c4a56fb750769d36425b86289a67584182695df12f315735025aa0c82805` | 未找到同名或 SHA 匹配候选 |
| D1-03.signals | `modules/rally/.runtime/d1-person-motion-20261017/pose-local-flow-dense-01/D1-03-signals.npz` | `4369ba8128e3b12c1ff5dd67dd1ff4d1ce24346f00771a100342ab94a9fe75c7` | 未找到同名或 SHA 匹配候选 |
| D1-03.people | `modules/rally/.runtime/d1-person-motion-20261017/D1-03/players-v2.jsonl` | `c2f2d28e60410d8693c7f6780e664a8169cfc110aaa63b697599c5470edda961` | 未找到同名或 SHA 匹配候选 |
| D1-04.signals | `modules/rally/.runtime/d1-person-motion-20261017/pose-local-flow-dense-01/D1-04-signals.npz` | `0670ac33d07c9c230c80aa93038ec649359f660f275c9f76fc605ab8ee3fced7` | 未找到同名或 SHA 匹配候选 |
| D1-04.people | `modules/rally/.runtime/d1-person-motion-20261017/D1-04/players-v2.jsonl` | `f6e0bde0c2aed6430a5c35f1dc6301aa76fb23fa2e56f3f5b925ebaa908f0664` | 未找到同名或 SHA 匹配候选 |
| D2-01.signals | `modules/rally/.runtime/d2-current-algorithm-20261018/flow/D2-01-signals.npz` | `ba3a5a1fe47da0ab61fe3b7fa6da1c4647b9087f971e302d6dfe2445de7c8376` | 未找到同名或 SHA 匹配候选 |
| D2-01.people | `modules/rally/.runtime/d2-current-algorithm-20261018/D2-01/players-v2.jsonl` | `5c9c60699350e971383624293ed0a106a4f4a841ce264d149eb685b03f950e44` | 未找到同名或 SHA 匹配候选 |

## 检查边界

- 候选范围：原工作区 `modules/rally/.runtime/`（不存在）、`outputs/`（限定目录内文件名及 SHA）、任务明确允许的单个外部 tracknet 路径；并查看 `outputs/media-restore.json` 的迁移记录。
- 未修改、复制、删除、暂存或提交任何输入和 `outputs/` 内容；未运行模型。
- 输出仅说明本次限定范围内未找到匹配副本；不推断其他未授权目录中不存在副本。
