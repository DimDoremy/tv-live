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
