# 网站导航站

一个单页的网站导航站，用来集中管理常用网站。数据保存在服务器上，清理浏览器缓存、换电脑或换浏览器都不会丢失，并自动保留历史备份。

## 功能

- 按分组展示网站，自动显示网站图标，加载失败时显示首字母色块
- 搜索网站名称、网址和备注；按 `/` 聚焦搜索框，回车打开第一个结果，没有匹配时回车用百度搜索
- 编辑模式下添加、修改、删除网站和分组，支持批量粘贴添加
- 拖动调整网站顺序（可跨分组），拖动调整分组顺序，一键按名称排序（中文按拼音）
- 导入浏览器书签（按文件夹自动分组，重复网址跳过），导出为浏览器书签文件
- JSON 备份与恢复
- 数据保存到服务器，每次保存自动备份旧版本；可设置保存密码
- 多设备同时修改时检测冲突，不会悄悄覆盖别人的修改
- 服务器暂时连不上时，修改先暂存在浏览器，恢复后自动同步
- 支持深色模式和手机访问

## 文件说明

| 文件 | 说明 |
| --- | --- |
| `index.html` | 页面本身，所有样式和脚本（含 SortableJS）都内嵌在内，不依赖任何外部 CDN |
| `server.py` | 服务端，提供页面并读写数据，只用 Python 标准库 |
| `nav-hub.service` | systemd 服务文件，用于开机自启 |
| `README.md` | 本说明 |

运行后会自动生成数据目录：

```
/opt/nav/
├── index.html
├── server.py
├── icons/              # 可选，自定义网站图标
└── data/               # 自动生成，网页无法直接访问
    ├── data.json       # 导航数据
    └── backups/        # 历史备份，默认保留最近 100 份
```

## 环境要求

- Python 3.6 及以上（CentOS 7 自带的 python3 即可），无需安装任何第三方库
- 任意 Linux 发行版，使用 systemd 管理服务

检查 Python 版本：

```bash
python3 --version
```

## 部署

以下以部署到 `/opt/nav`、监听 8080 端口为例。

### 1. 复制文件并创建运行用户

```bash
sudo mkdir -p /opt/nav
sudo cp index.html server.py /opt/nav/

# 创建一个不能登录的专用系统用户
sudo useradd -r -s /sbin/nologin nav
sudo chown -R nav:nav /opt/nav
```

### 2. 配置并启动服务

编辑 `nav-hub.service`，把 `NAV_TOKEN=` 后面改成你自己的保存密码：

```ini
Environment=NAV_TOKEN=你的密码
```

不需要密码的话删掉这一行，此时任何能访问页面的人都能修改数据。

```bash
sudo cp nav-hub.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nav-hub
sudo systemctl status nav-hub
```

状态显示 `active (running)` 即启动成功，浏览器访问 `http://服务器IP:8080`。

### 3. 放行防火墙端口

CentOS / RHEL / Rocky：

```bash
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

Ubuntu（启用了 ufw 时）：

```bash
sudo ufw allow 8080/tcp
```

### 4. 使用 Nginx 反向代理（可选）

需要用域名、80/443 端口或 HTTPS 访问时，在 Nginx 中添加：

```nginx
server {
    listen 80;
    server_name nav.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        client_max_body_size 5m;
    }
}
```

此时可以把服务改为只监听本机：`ExecStart` 中用 `--bind 127.0.0.1`，8080 端口也不必对外开放。

CentOS / RHEL 上如果 Nginx 转发报 502，且 `/var/log/nginx/error.log` 中有 `permission denied`，是 SELinux 拦截，执行：

```bash
sudo setsebool -P httpd_can_network_connect 1
```

### server.py 启动参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--bind` | `0.0.0.0` | 监听地址 |
| `--port` | `8080` | 监听端口 |
| `--web` | `server.py` 所在目录 | 静态文件目录（放 `index.html` 的目录） |
| `--data` | `<server.py 所在目录>/data` | 数据与备份目录 |

环境变量 `NAV_TOKEN`：设置后保存数据需要密码，查看不需要。

## 使用说明

- **搜索**：按 `/` 聚焦搜索框，输入关键字过滤；回车打开第一个结果；`Esc` 清空。
- **编辑**：点右上角“编辑”进入编辑模式。
  - 点网站卡片修改，点右上角 × 删除，点“+ 添加网站”新增
  - 拖动卡片调整顺序，也可以拖到其他分组
  - 拖动侧栏中的分组名，或分组标题左侧的 ⠿，调整分组顺序
  - 每个分组提供“批量添加”“重命名”“按名称排序”“删除分组”
  - 点页面标题可以修改标题
  - 手机上长按约 0.2 秒再拖动
- **批量添加**：每行一个网站，名称和网址之间用空格、逗号或竖线分隔；只写网址时名称使用域名。例如：

  ```
  阿里云控制台 https://home.console.aliyun.com
  github.com
  Grafana | http://10.0.0.5:3000
  ```

- **首次保存**：设置了密码时，每台设备第一次保存会要求输入密码，之后浏览器会记住。

### 网站图标

默认自动加载网站根目录的 `favicon.ico`，失败时显示首字母色块。内网地址或图标不在根目录的网站，可以自定义图标：把图片放到 `/opt/nav/icons/`，然后在修改网站时把“图标地址”填为 `icons/xxx.png`，也可以直接填图片网址。

### 导入浏览器书签

1. 在浏览器中导出书签：
   - Chrome：`Ctrl+Shift+O` → 右上角 ⋮ → 导出书签
   - Edge：`Ctrl+Shift+O` → 右上角 … → 导出收藏夹
   - Firefox：`Ctrl+Shift+O` → 导入和备份 → 导出书签到 HTML
2. 在导航站点“导入/导出”，在“导入浏览器书签”中选择导出的 `.html` 文件。

按最内层书签文件夹分组，同名分组会合并，已存在的网址会跳过，只导入 http/https 链接。

### 导出到浏览器书签

在“导入/导出”中点“下载书签文件”，再在浏览器中导入：

- Chrome：`Ctrl+Shift+O` → ⋮ → 导入书签
- Edge：`Ctrl+Shift+O` → … → 导入收藏夹 → 收藏夹或书签 HTML 文件
- Firefox：导入和备份 → 从 HTML 导入书签

所有网站会放在一个与导航站标题同名的文件夹中，每个分组为一个子文件夹。浏览器导入时不会去重，重复导入前请先删除旧文件夹。

## 数据与备份

- 数据文件：`/opt/nav/data/data.json`，写入时先写临时文件再原子替换，中途断电不会损坏。
- 每次保存前，旧版本会复制到 `/opt/nav/data/backups/`，文件名带时间戳，默认保留最近 100 份（修改 `server.py` 中的 `KEEP_BACKUPS` 可调整）。
- 页面“导入/导出”中也可以复制 JSON 备份，或粘贴备份恢复。

### 从备份恢复

```bash
ls -lt /opt/nav/data/backups/ | head
sudo cp /opt/nav/data/backups/data-20260929-112900-123.json /opt/nav/data/data.json
sudo chown nav:nav /opt/nav/data/data.json
```

无需重启服务，刷新页面即可看到恢复后的数据。

### 定期异地备份（建议）

```bash
# crontab -e，每天凌晨 2 点打包备份
0 2 * * * tar czf /backup/nav-$(date +\%Y\%m\%d).tar.gz -C /opt/nav data
```

### 迁移浏览器里已有的数据

服务器上还没有 `data.json` 时，第一次打开页面会把当前浏览器里已有的内容上传作为初始数据。所以之前用过单机版的话，先用那个浏览器打开一次新部署的页面。

## 多设备与冲突

- 所有设备打开的都是服务器上的同一份数据；切回页面标签时会自动拉取最新数据。
- 如果 A 设备已保存修改，B 设备还开着旧页面又去修改，B 会提示“数据已在别处修改”，可以选择：
  - **载入服务器版本**：放弃 B 刚才的修改
  - **用我的覆盖**：用 B 的内容替换服务器数据，被替换的版本保留在备份目录中
- 服务器连不上时，状态栏会显示“连不上服务器，更改暂存本浏览器”，恢复后自动同步。

## 升级

替换文件后重启服务即可，数据目录不受影响：

```bash
sudo cp index.html server.py /opt/nav/
sudo chown nav:nav /opt/nav/index.html /opt/nav/server.py
sudo systemctl restart nav-hub
```

`index.html` 中内嵌的默认网站列表只在服务器没有数据时使用，替换页面不会覆盖已有数据。

## 常见问题

**`chown: 无效的用户: "www-data:www-data"`**
CentOS / RHEL 没有 `www-data` 用户。按上文创建 `nav` 用户，并确认 service 文件中是 `User=nav`、`Group=nav`。

**`ImportError: cannot import name 'ThreadingHTTPServer'`**
使用的是旧版 `server.py`，请更新到当前版本（已兼容 Python 3.6）。

**提示“密码不正确”**
查看服务实际使用的密码：

```bash
sudo systemctl show nav-hub -p Environment
```

- 仍是 `请改成你的密码`：未修改或未重新加载。修改 `/etc/systemd/system/nav-hub.service` 后执行 `sudo systemctl daemon-reload && sudo systemctl restart nav-hub`。
- 密码含 `%`：systemd 中需写成 `%%`。
- 密码含空格：写成 `Environment="NAV_TOKEN=my pass"`。
- 建议使用字母、数字和符号，避免中文密码。

改好后在页面弹框中重新输入即可，浏览器会用新密码覆盖记住的旧密码。在服务器上验证密码：

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X PUT \
  -H "X-Nav-Token: 你的密码" -H "Content-Type: application/json" \
  --data-binary @/opt/nav/data/data.json http://127.0.0.1:8080/data.json
```

返回 `200` 表示密码正确（该命令只是把现有数据原样写回）。

**状态栏显示“仅保存在本浏览器”**
页面是双击用 `file://` 打开的，或服务端不支持保存。请通过 `http://服务器IP:8080` 访问。

**状态栏显示“连不上服务器”**
检查服务状态和端口：

```bash
sudo systemctl status nav-hub
sudo journalctl -u nav-hub -n 30
ss -lntp | grep 8080
```

**Nginx 反代后 502**
先确认 `curl http://127.0.0.1:8080/` 正常；CentOS / RHEL 上执行 `sudo setsebool -P httpd_can_network_connect 1`。

**部分网站图标显示空白或首字母**
该网站的图标不在根目录 `favicon.ico`，或是内网地址。可在修改网站时填写“图标地址”。

## 安全说明

- 查看页面不需要密码，任何能访问该地址的人都能看到导航内容；请勿在备注中保存账号密码等敏感信息。
- 保存密码以明文形式在请求头中传输，公网访问时请通过 Nginx 配置 HTTPS。
- 网页无法直接访问 `data/` 目录和 `server.py`。

## 第三方组件

- [SortableJS](https://github.com/SortableJS/Sortable) 1.15.6，MIT 许可，已内嵌在 `index.html` 中。
