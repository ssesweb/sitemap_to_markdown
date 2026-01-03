import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import httpx
import asyncio
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from urllib.parse import urlparse
import logging
import os
import datetime
import re

# --- 配置 ---
# 更改为安全端口 9090，避免浏览器 ERR_UNSAFE_PORT 错误
PORT = 9090
# 并发限制，防止请求过快被封
CONCURRENCY_LIMIT = 5
# 忽略的标签 (通常是导航、侧边栏、脚本)
IGNORE_TAGS = ['script', 'style', 'nav', 'footer', 'iframe', 'noscript', 'aside', 'header']

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SitemapScraper")

app = FastAPI()

# 存放生成的文件的临时目录
OUTPUT_DIR = "downloads"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# --- HTML 界面模板 ---
html_template = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sitemap 转 Markdown 提取器</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .terminal-logs {
            font-family: 'Courier New', Courier, monospace;
            background-color: #1e1e1e;
            color: #00ff00;
            padding: 1rem;
            height: 400px;
            overflow-y: auto;
            border-radius: 0.5rem;
            font-size: 0.85rem;
            line-height: 1.4;
        }
        .log-info { color: #4ade80; }
        .log-warn { color: #facc15; }
        .log-error { color: #f87171; }
        .log-system { color: #60a5fa; font-weight: bold; }
        
        /* 简单的 Markdown 预览样式 */
        .loading-spinner {
            border: 4px solid rgba(0, 0, 0, 0.1);
            width: 36px;
            height: 36px;
            border-radius: 50%;
            border-left-color: #09f;
            animation: spin 1s ease infinite;
            display: inline-block;
            vertical-align: middle;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="bg-gray-100 min-h-screen py-10 px-4">

    <div class="max-w-4xl mx-auto bg-white shadow-lg rounded-xl overflow-hidden">
        <div class="bg-indigo-600 p-6">
            <h1 class="text-2xl font-bold text-white flex items-center gap-2">
                <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                Sitemap to Markdown
            </h1>
            <p class="text-indigo-200 mt-2">输入 Sitemap.xml 地址，一键爬取所有页面并合并为 Markdown 文档。</p>
        </div>

        <div class="p-6 space-y-6">
            <!-- 输入区域 -->
            <div class="flex gap-4">
                <input type="text" id="sitemapUrl" placeholder="https://example.com/sitemap.xml" 
                       class="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition"
                       value="https://example.com/sitemap.xml">
                <button onclick="startScraping()" id="startBtn"
                        class="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg transition shadow-md flex items-center gap-2">
                    <span>开始提取</span>
                </button>
            </div>

            <!-- 状态与下载 -->
            <div id="statusArea" class="hidden bg-gray-50 p-4 rounded-lg border border-gray-200 flex justify-between items-center">
                <div class="flex items-center gap-3">
                    <div id="spinner" class="loading-spinner"></div>
                    <span id="statusText" class="text-gray-700 font-medium">正在处理中...</span>
                </div>
                <a id="downloadBtn" href="#" class="hidden px-5 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition shadow-sm">
                    下载 Markdown
                </a>
            </div>

            <!-- 日志终端 -->
            <div>
                <div class="flex justify-between items-center mb-2">
                    <label class="text-sm font-semibold text-gray-600">运行日志</label>
                    <button onclick="clearLogs()" class="text-xs text-gray-500 hover:text-gray-700">清空日志</button>
                </div>
                <div id="logs" class="terminal-logs">
                    <div class="log-system">> 等待任务开始...</div>
                </div>
            </div>
        </div>
        
        <div class="bg-gray-50 px-6 py-3 text-xs text-gray-500 border-t text-center">
            Designed for Python FastAPI • Localhost Port 9090
        </div>
    </div>

    <script>
        let ws;
        const logDiv = document.getElementById('logs');
        const statusArea = document.getElementById('statusArea');
        const statusText = document.getElementById('statusText');
        const downloadBtn = document.getElementById('downloadBtn');
        const startBtn = document.getElementById('startBtn');
        const spinner = document.getElementById('spinner');

        function appendLog(msg, type='info') {
            const div = document.createElement('div');
            const time = new Date().toLocaleTimeString();
            div.className = `log-${type} mb-1`;
            div.innerText = `[${time}] ${msg}`;
            logDiv.appendChild(div);
            logDiv.scrollTop = logDiv.scrollHeight;
        }

        function clearLogs() {
            logDiv.innerHTML = '<div class="log-system">> 日志已清空</div>';
        }

        function startScraping() {
            const url = document.getElementById('sitemapUrl').value;
            // 修正 WebSocket 连接逻辑：使用当前页面的 host 和 port，不进行硬编码
            const host = window.location.host;

            if (!url) return console.error('请输入有效的 Sitemap URL'); // 改用 console.error 避免 alert

            // UI Reset
            startBtn.disabled = true;
            startBtn.classList.add('opacity-50', 'cursor-not-allowed');
            statusArea.classList.remove('hidden');
            downloadBtn.classList.add('hidden');
            spinner.style.display = 'inline-block';
            statusText.innerText = '正在初始化...';
            clearLogs();

            // WebSocket Connection
            // 协议也根据当前页面动态确定 (ws: for http, wss: for https)
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            // 使用当前页面加载的 host:port 进行连接
            ws = new WebSocket(`${protocol}//${host}/ws`);

            ws.onopen = () => {
                appendLog(`已连接到服务器 (${protocol}//${host}/ws)，开始请求: ${url}`, 'system');
                ws.send(url);
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                if (data.type === 'log') {
                    appendLog(data.message, 'info');
                } else if (data.type === 'error') {
                    appendLog(data.message, 'error');
                } else if (data.type === 'progress') {
                    statusText.innerText = data.message;
                } else if (data.type === 'complete') {
                    appendLog('任务完成！', 'system');
                    statusText.innerText = '处理完成！';
                    spinner.style.display = 'none';
                    downloadBtn.href = data.download_url;
                    downloadBtn.classList.remove('hidden');
                    startBtn.disabled = false;
                    startBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                    ws.close();
                }
            };

            ws.onclose = () => {
                // 仅在任务未完成时显示断开连接错误
                if (statusText.innerText !== '处理完成！') {
                    startBtn.disabled = false;
                    startBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                    spinner.style.display = 'none';
                    appendLog('连接已断开', 'error');
                }
            };

            ws.onerror = (err) => {
                appendLog('WebSocket 连接错误', 'error');
                console.error(err);
            };
        }
    </script>
</body>
</html>
"""

# --- 后端逻辑 ---

@app.get("/")
async def get_html():
    return HTMLResponse(html_template)

@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename, media_type='text/markdown')
    return {"error": "File not found"}

async def fetch_url_content(client: httpx.AsyncClient, url: str, semaphore: asyncio.Semaphore):
    """
    抓取单个 URL 并转换为 Markdown
    """
    async with semaphore:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = await client.get(url, headers=headers, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
            
            # 使用 BeautifulSoup 清理 HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 获取标题
            title = soup.title.string if soup.title else url
            title = title.strip()
            
            # 移除无用标签
            for tag in IGNORE_TAGS:
                for element in soup.find_all(tag):
                    element.decompose()

            # 尝试定位主要内容区域 (简单的启发式)
            # 很多文档网站使用 <main>, <article>, 或者 id="content"
            main_content = soup.find('main') or soup.find('article') or soup.find(id='content') or soup.find(class_='content') or soup.body

            if not main_content:
                main_content = soup # 如果实在找不到，就用整个 soup

            # 转为 Markdown
            # heading_style="atx" 使用 # ## 格式
            md_content = md(str(main_content), heading_style="atx", strip=['a']) 
            # strip=['a'] 可选：如果想保留链接则去掉这个参数。这里为了纯净阅读，可能会希望保留链接，如下：
            md_content = md(str(main_content), heading_style="atx")

            # 稍微清理一下多余的空行
            md_content = re.sub(r'\n{3,}', '\n\n', md_content)
            
            return {
                "url": url,
                "title": title,
                "content": md_content,
                "success": True
            }

        except Exception as e:
            return {
                "url": url,
                "error": str(e),
                "success": False
            }

async def parse_sitemap(client: httpx.AsyncClient, sitemap_url: str):
    """
    递归解析 Sitemap XML
    """
    urls = []
    try:
        headers = {"User-Agent": "SitemapScraperBot/1.0"}
        response = await client.get(sitemap_url, headers=headers, timeout=30.0)
        
        # 简单的 XML 解析
        root = ET.fromstring(response.content)
        
        # 处理命名空间 (sitemap 经常有 xmlns)
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        # 查找所有 loc (可能是 url 或者是 sitemap index)
        # 尝试查找 <url> 下的 <loc>
        for url_entry in root.findall('.//ns:url/ns:loc', namespace) or root.findall('.//url/loc'):
            urls.append(url_entry.text)
            
        # 尝试查找 <sitemap> 下的 <loc> (Sitemap Index)
        # 如果是 Index，需要递归，这里简化处理，只做一层提示或简单扁平化，或者忽略
        # 实际应用中可以递归调用，但为了防止无限递归，这里仅记录
        
    except Exception as e:
        logger.error(f"Error parsing sitemap {sitemap_url}: {e}")
        raise e
        
    return list(set(urls)) # 去重

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client = httpx.AsyncClient()
    
    try:
        sitemap_url = await websocket.receive_text()
        
        # 1. 解析 Sitemap
        await websocket.send_json({"type": "log", "message": f"开始解析 Sitemap: {sitemap_url}"})
        await websocket.send_json({"type": "progress", "message": "正在获取 URL 列表..."})
        
        try:
            urls = await parse_sitemap(client, sitemap_url)
        except Exception as e:
            await websocket.send_json({"type": "error", "message": f"Sitemap 解析失败: {str(e)}"})
            await client.aclose()
            return

        if not urls:
            await websocket.send_json({"type": "error", "message": "Sitemap 中未找到有效的 URL"})
            await client.aclose()
            return

        total_urls = len(urls)
        await websocket.send_json({"type": "log", "message": f"找到 {total_urls} 个页面，准备开始抓取..."})

        # 2. 并发抓取
        results = []
        semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
        tasks = [fetch_url_content(client, url, semaphore) for url in urls]
        
        completed_count = 0
        
        # 使用 as_completed 处理进度
        for future in asyncio.as_completed(tasks):
            result = await future
            completed_count += 1
            
            if result['success']:
                await websocket.send_json({"type": "log", "message": f"[{completed_count}/{total_urls}] 成功: {result['title'][:30]}..."})
            else:
                await websocket.send_json({"type": "error", "message": f"[{completed_count}/{total_urls}] 失败: {result['url']} ({result.get('error')})"})
            
            # 更新状态文字
            await websocket.send_json({"type": "progress", "message": f"正在抓取: {completed_count}/{total_urls}"})
            
            if result['success']:
                results.append(result)

        # 3. 生成 Markdown 文件
        await websocket.send_json({"type": "progress", "message": "正在生成最终文档..."})
        
        domain = urlparse(sitemap_url).netloc.replace('.', '_')
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{domain}_full_{timestamp}.md"
        filepath = os.path.join(OUTPUT_DIR, filename)

        # 构建文件内容
        toc_lines = ["# 目录索引 (Table of Contents)\n"]
        body_lines = []
        
        # 按照 URL 排序，尽量保持一定的逻辑顺序
        results.sort(key=lambda x: x['url'])

        toc_lines.append(f"**源 Sitemap:** [{sitemap_url}]({sitemap_url})\n")
        toc_lines.append(f"**生成时间:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        toc_lines.append(f"**包含页面数:** {len(results)}\n")
        toc_lines.append("---\n")

        for idx, res in enumerate(results):
            # 创建锚点 ID
            anchor_id = f"page-{idx}"
            title = res['title']
            url = res['url']
            
            # 写入目录
            toc_lines.append(f"- [{title}](#{anchor_id})  *({url})*")
            
            # 写入正文
            body_lines.append(f"\n\n<div id='{anchor_id}'></div>\n\n") # HTML 锚点比较稳
            body_lines.append(f"# {title}\n\n")
            body_lines.append(f"> 原文链接: [{url}]({url})\n\n")
            body_lines.append("---\n\n")
            body_lines.append(res['content'])
            body_lines.append("\n\n---\n\n") # 页面分隔符

        final_content = "\n".join(toc_lines) + "\n\n" + "# 正文内容\n\n" + "".join(body_lines)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(final_content)

        await websocket.send_json({
            "type": "complete", 
            "download_url": f"/download/{filename}",
            "message": "完成！"
        })

    except Exception as e:
        await websocket.send_json({"type": "error", "message": f"发生未知错误: {str(e)}"})
        logger.error(f"WebSocket error: {e}")
    finally:
        await client.aclose()

if __name__ == "__main__":
    print(f"应用已启动: http://localhost:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
