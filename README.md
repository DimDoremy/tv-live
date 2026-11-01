# tv-live

给客厅 Hisense VIDAA 电视（Android 8.1，`192.168.1.21`）用的直播源订阅仓库。

电视端用 **MyTV**（`com.github.mytv.android`）订阅本仓库的 `live.m3u`，
不依赖家里任何一台电脑开机，只要电视联网即可自行拉取更新。

## 订阅地址

| 线路 | URL | 说明 |
|---|---|---|
| jsDelivr（推荐） | `https://cdn.jsdelivr.net/gh/DimDoremy/tv-live@main/live.m3u` | CDN 加速，国内多数网络可直连 |
| gh-proxy 镜像 | `https://gh-proxy.com/https://raw.githubusercontent.com/DimDoremy/tv-live/main/live.m3u` | 镜像，兜底用 |
| GitHub 直连 | `https://raw.githubusercontent.com/DimDoremy/tv-live/main/live.m3u` | 原生地址，部分网络会被干扰 |

## 文件

- `base.m3u` —— **人工维护的基准列表**（435 频道 / 43 分组），每条线路都用电视本机实测可达。脚本不会改动它。
- `live.m3u` —— 对外发布的列表，由 `scripts/refresh.py` 用 `base.m3u` 生成：
  保留基准线路在前，再从国内每日更新的上游列表为同一频道补充最多 2 条线路。
- `scripts/refresh.py` —— 合并脚本，不做网络测速（CI 在境外，测速结果对国内电视没有参考意义）。
- `.github/workflows/refresh.yml` —— 每天 11:00（北京时间）自动重跑并提交，也可手动触发。

## 设计取舍

- **不在 CI 里做可用性测试**：GitHub runner 在境外，大量国内 IPTV 节点对境外 IP 不提供服务，
  在 runner 上测出的“死链”在电视上往往是可用的，反之亦然。可用性只以电视侧实测为准。
- **上游只补线路、不引新频道**：上游列表里大量 WebView/JS 类型条目（央视频网页版等）会导致
  电视端卡在“正在加载网页”，因此只接受 `http(s)` 直链，并且只挂到已存在的频道上。
- **EPG 与台标**沿用可直连的 gitee 源：
  - `https://gitee.com/mytv-android/myepg/raw/master/output/epg.gz`
  - `https://gitee.com/mytv-android/myTVlogo/raw/main/img/…`

## 电视端配置

1. MyTV → 设置 → 订阅源 → 自定义订阅源 → 添加其他订阅源 → 直接输入
2. 类型选 **远程**，链接填上面的订阅地址
3. 设为当前，点「刷新全部」

## 更新基准列表

在本机改好并实测后：

```bash
cp <新的 m3u> base.m3u
python3 scripts/refresh.py     # 生成 live.m3u
git add base.m3u live.m3u && git commit -m "update base" && git push
```

## 已知行为（重要）

MyTV 会给名字能对上的央视/卫视频道**自动追加它自带的“央视网 / 央视频”网页源**，并且优先尝试。
这些网页源在国内时快时慢，偶尔会停在“播放失败 · 加载超时”。

处理方式：

- 遥控器按 **OK** 打开播放控制 → **切换线路**（或按左右方向键），切到 m3u8 线路即可；
- 或先退出播放器，进「全部频道」重新点一次该频道，第二次通常会落到 m3u8 线路；
- 该行为与订阅源是本地文件还是远程地址无关，属于 App 自身逻辑。

## 离线兜底

电视上仍保留了一份本地副本 `/storage/emulated/0/Download/tv_live.m3u`。
若远程地址哪天被墙/失效，进「添加其他订阅源 → 本地」指向它即可继续看，不需要电脑。

## 电视端播放器：StreamVault（推荐）

MyTV 会自动插入它的“央视频/央视网”网页源，实测经常卡在网页加载，因此改用纯 IPTV 播放器。

- 应用：**StreamVault** `com.streamvault.app`（开源，TV 优先界面，Media3 内核）
- APK：`https://github.com/Davidona/StreamVault-IPTV/releases/latest`
- 安装：`adb install -r StreamVault-1.2.3.apk`（本机 TV 为 armeabi-v7a，该包已带 v7a 库）
- 入口：电视「应用」列表最后一行 → StreamVault

### 配置

1. 首次启动 → 设置提供商 → 来源类型 **URL**
2. M3U URL 填：`https://cdn.jsdelivr.net/gh/DimDoremy/tv-live@main/live.m3u`
3. 也可以走「从手机添加」：电视显示 `http://<TV-IP>:<端口>/pair?t=...`，在同一局域网用电脑打开，
   表单字段 `type=m3u`、`name`、`m3uUrl`，POST 到 `/submit` 即可（比遥控器打字快得多）

### 本机电视（MSD6A848）必做的两个开关

设置 → 播放 → 通用：

- **匹配内容帧率** → 关（开关会触发 HDMI 模式切换，容易黑屏/解码失败）
- **系统媒体会话** → 关（App 自己也提示：该机开启后播放器可能崩溃）

若出现“播放失败 / 解码器初始化失败”（logcat: `OMX.MS.AVC.Decoder ... DECODER_INIT_FAILED`），
说明硬件解码器被占用：先关掉 MyTV / 影视仓等其他播放器再进 StreamVault，重新选台即可。
本机实测 CCTV-1（1080p H.264/TS）与东方卫视可正常出画，EPG 来自 m3u 的 `x-tvg-url`。
