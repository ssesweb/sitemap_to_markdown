# Sitemap to Markdown Scraper

这是一个基于 Python **FastAPI** 框架和 **WebSocket** 技术的网页提取工具。它可以自动解析网站的 `sitemap.xml`，并发抓取其中包含的所有页面，并将其转换为整洁的 **Markdown** 文档。

## 核心功能

* **Sitemap 解析**：支持标准的 XML Sitemap 格式提取。
* **异步并发抓取**：利用 `httpx` 和 `asyncio` 实现高效的并发请求。
* **智能 HTML 转 MD**：使用 `BeautifulSoup` 清理冗余标签（如脚本、导航栏、侧边栏），并由 `markdownify` 生成格式规范的 Markdown。
* **实时交互界面**：通过 WebSocket 提供实时运行日志和进度反馈。
* **自动生成目录**：最终生成的 Markdown 文件包含自动生成的目录索引，并支持锚点跳转。
* **本地文件下载**：抓取完成后，自动合并并提供下载链接。

## 环境要求

* Python 3.8+
* 依赖库：`fastapi`, `uvicorn`, `httpx`, `beautifulsoup4`, `markdownify`

## 快速开始

### 1. 安装依赖

```bash
git clone https://github.com/ssesweb/sitemap_to_markdown.git
cd sitemap_to_markdown
pip install fastapi uvicorn httpx beautifulsoup4 markdownify
```

### 2. 运行应用

**Bash**

```
python app.py
```

### 3. 访问界面

在浏览器中打开：`http://localhost:9090`

1. 在输入框中填入目标网站的 `sitemap.xml` 地址。
2. 点击  **“开始提取”** 。
3. 在终端日志窗口实时查看抓取进度。
4. 完成后点击 **“下载 Markdown”** 按钮获取结果。

## 详细配置

您可以在代码顶部的 `--- 配置 ---` 部分修改以下参数：

| **参数**          | **说明**                   | **默认值**                      |
| ------------------------- | ---------------------------------- | --------------------------------------- |
| `PORT`              | 服务运行的端口号                 | `9090`                            |
| `CONCURRENCY_LIMIT` | 并发请求限制（防止请求过快被封） | `5`                               |
| `IGNORE_TAGS`       | HTML 转换时需要剔除的标签        | `['script', 'style', 'nav', ...]` |
| `OUTPUT_DIR`        | 生成文件的存放目录               | `downloads`                       |

## 技术栈

* **后端** : [FastAPI](https://fastapi.tiangolo.com/) - 高性能异步 Web 框架。
* **爬虫** : [httpx](https://www.python-httpx.org/) - 支持异步的 HTTP 客户端。
* **解析** : [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) & `xml.etree.ElementTree`。
* **转换** : [markdownify](https://github.com/matthewwithanm/python-markdownify) - 将 HTML 转化为 Markdown。
* **前端** : [Tailwind CSS](https://tailwindcss.com/) - 响应式 UI 样式。

## 注意事项

1. **权限与合规** ：请确保您有权抓取目标网站的内容，并遵守网站的 `robots.txt` 协议。
2. **并发压力** ：如果抓取大型网站，请适当降低 `CONCURRENCY_LIMIT` 以免对目标服务器造成过大压力。
3. **内容提取** ：程序内置了简单的启发式算法来寻找网页正文（如 `<main>` 或 `<article>` 标签），对于结构极特殊的网站可能需要调整提取逻辑。

---

### 说明与建议

1. **文档结构**：README 遵循了标准的开源项目格式，包括功能介绍、环境配置、快速上手和技术栈说明。
2. **安全性提示**：在注意事项中加入了关于爬虫合规性和服务器压力的提醒，这对开发者来说是非常重要的。
3. **配置表**：使用了 Markdown 表格，让用户一眼就能看到代码中哪些变量是可以自定义的。
