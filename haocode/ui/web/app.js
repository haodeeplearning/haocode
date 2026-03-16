var chatContainer = document.getElementById('chat-container');
var messageBuffer = {};
var longTextStore = {};
// 🌟 检测用户是否在页面底部附近（容差 150px）
function isNearBottom() {
    return (window.innerHeight + window.scrollY) >= (document.body.scrollHeight - 150);
}

// ==================== Markdown 渲染器配置 ====================
var renderer = new marked.Renderer();

renderer.code = function(obj) {
    var code = (typeof obj === 'string') ? obj : (obj.text || '');
    var lang = (typeof obj === 'string') ? (arguments[1] || '') : (obj.lang || '');
    var langLabel = lang ? lang : 'code';

    return '<div class="code-block-wrapper">'
        + '<div class="code-header">'
        + '<span class="code-lang-label">' + langLabel + '</span>'
        + '<div class="code-header-actions">'
        + '<button class="fold-btn">展开</button>'
        + '<button class="copy-btn">'
        + '<svg class="icon-copy" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>'
        + '<svg class="icon-check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:none"><polyline points="20 6 9 17 4 12"/></svg>'
        + '<span class="btn-text">复制</span>'
        + '</button>'
        + '</div>'
        + '</div>'
        + '<pre class="code-body collapsed"><code class="language-' + lang + '">' + code + '</code></pre>'
        + '</div>';
};

marked.setOptions({ renderer: renderer, breaks: true });

// ==================== 全局事件委托 ====================
chatContainer.addEventListener('click', function(e) {
    var copyBtn = e.target.closest('.copy-btn');
    if (copyBtn) {
        var wrapper = copyBtn.closest('.code-block-wrapper');
        var rawCode = wrapper.querySelector('code').textContent;
        copyToClipboard(rawCode).then(function() {
            copyBtn.classList.add('copied');
            copyBtn.querySelector('.icon-copy').style.display = 'none';
            copyBtn.querySelector('.icon-check').style.display = 'inline';
            copyBtn.querySelector('.btn-text').textContent = '已复制';
            setTimeout(function() {
                copyBtn.classList.remove('copied');
                copyBtn.querySelector('.icon-copy').style.display = 'inline';
                copyBtn.querySelector('.icon-check').style.display = 'none';
                copyBtn.querySelector('.btn-text').textContent = '复制';
            }, 2000);
        });
        return;
    }

    var foldBtn = e.target.closest('.fold-btn');
    if (foldBtn) {
        var wrapper = foldBtn.closest('.code-block-wrapper');
        var pre = wrapper.querySelector('.code-body');
        pre.classList.toggle('collapsed');
        foldBtn.textContent = pre.classList.contains('collapsed') ? '展开' : '收起';
        return;
    }

    var card = e.target.closest('.long-text-card');
    if (card) {
        showContentModal(card.getAttribute('data-msg-id'));
        return;
    }
});

document.addEventListener('click', function(e) {
    if (e.target.closest('.modal-close-btn')) { closeContentModal(); return; }
    var overlay = e.target.closest('.content-modal-overlay');
    if (overlay && e.target === overlay) { closeContentModal(); return; }
});

// ==================== 剪贴板 ====================
function copyToClipboard(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px;opacity:0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    return new Promise(function(resolve, reject) {
        try { document.execCommand('copy'); resolve(); }
        catch (err) { reject(err); }
        finally { ta.remove(); }
    });
}

// ==================== 模态框 ====================
function showContentModal(msgId) {
    var text = longTextStore[msgId];
    if (!text) return;
    closeContentModal();

    var overlay = document.createElement('div');
    overlay.className = 'content-modal-overlay';

    var modal = document.createElement('div');
    modal.className = 'content-modal';

    var header = document.createElement('div');
    header.className = 'modal-header';
    var title = document.createElement('span');
    title.textContent = '文件内容';
    var closeBtn = document.createElement('button');
    closeBtn.className = 'modal-close-btn';
    closeBtn.innerHTML = '✕';
    header.appendChild(title);
    header.appendChild(closeBtn);

    var body = document.createElement('pre');
    body.className = 'modal-body';
    body.textContent = text;

    modal.appendChild(header);
    modal.appendChild(body);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    requestAnimationFrame(function() { overlay.classList.add('visible'); });
}

function closeContentModal() {
    var overlay = document.querySelector('.content-modal-overlay');
    if (overlay) {
        overlay.classList.remove('visible');
        setTimeout(function() { overlay.remove(); }, 200);
    }
}


// ==================== 消息创建 ====================
function createMessage(msgId, role, initialText, senderName) {
    initialText = initialText || '';
    senderName = senderName || '';

    var welcome = document.querySelector('.welcome-screen');
    if (welcome) welcome.style.display = 'none';

    var wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper ' + role;
    wrapper.id = msgId;

    var avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.innerText = role === 'user' ? 'U' : 'AI';

    var content = document.createElement('div');
    content.className = 'message-content';

    var nameLabel = document.createElement('div');
    nameLabel.className = 'sender-name';
    nameLabel.innerText = senderName || (role === 'user' ? 'You' : 'Assistant');
    content.appendChild(nameLabel);

    var replyDiv = document.createElement('div');
    replyDiv.className = 'reply-content markdown-body';
    
    // 🌟 修复 1：不管是用户还是 AI，如果有初始文本，直接渲染
    if (initialText) {
        if (role === 'user') {
            replyDiv.innerText = initialText; // 用户保持纯文本
        } else {
            replyDiv.innerHTML = marked.parse(initialText); // AI 走 Markdown 渲染
        }
    }
    content.appendChild(replyDiv);

    wrapper.appendChild(avatar);
    wrapper.appendChild(content);
    chatContainer.appendChild(wrapper);

    // 🌟 修复 2：千万不能写死成 ''，必须把 initialText 存进缓存！
    // 这样紧接着执行 finishMessage 时，才不会被空字符串覆盖！
    messageBuffer[msgId] = { reasoning: '', content: initialText };
    
    wrapper.classList.add('streaming');
    softScroll();
}


// ==================== 长文本消息 ====================
function createLongMessage(msgId, role, fullText, senderName, sizeKb) {
    senderName = senderName || 'You';
    var welcome = document.querySelector('.welcome-screen');
    if (welcome) welcome.style.display = 'none';

    longTextStore[msgId] = fullText;
    var lineCount = fullText.split('\n').length;

    var wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper ' + role;
    wrapper.id = msgId;

    var avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.innerText = 'U';

    var content = document.createElement('div');
    content.className = 'message-content';

    var nameLabel = document.createElement('div');
    nameLabel.className = 'sender-name';
    nameLabel.innerText = senderName;
    content.appendChild(nameLabel);

    content.appendChild(buildAttachmentCard(msgId, fullText, sizeKb, lineCount));

    wrapper.appendChild(avatar);
    wrapper.appendChild(content);
    chatContainer.appendChild(wrapper);

    messageBuffer[msgId] = { reasoning: '', content: '' };
    softScroll();
}

// ==================== 带附件的用户消息 ====================
function createUserMessageWithAttachments(msgId, plainText, attachments) {
    var welcome = document.querySelector('.welcome-screen');
    if (welcome) welcome.style.display = 'none';

    var wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper user';
    wrapper.id = msgId;

    var avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.innerText = 'U';

    var content = document.createElement('div');
    content.className = 'message-content';

    var nameLabel = document.createElement('div');
    nameLabel.className = 'sender-name';
    nameLabel.innerText = 'You';
    content.appendChild(nameLabel);

    var cardsContainer = document.createElement('div');
    cardsContainer.className = 'attachments-container';
    for (var i = 0; i < attachments.length; i++) {
        var att = attachments[i];
        var attId = msgId + '-att-' + i;
        longTextStore[attId] = att.content;
        cardsContainer.appendChild(buildAttachmentCard(attId, att.content, att.size_kb, att.lines));
    }
    content.appendChild(cardsContainer);

    if (plainText && plainText.trim()) {
        var replyDiv = document.createElement('div');
        replyDiv.className = 'reply-content markdown-body';
        replyDiv.innerText = plainText;
        content.appendChild(replyDiv);
    }

    wrapper.appendChild(avatar);
    wrapper.appendChild(content);
    chatContainer.appendChild(wrapper);

    messageBuffer[msgId] = { reasoning: '', content: '' };
    softScroll();
}

// ==================== 附件卡片构建器 ====================
function buildAttachmentCard(id, text, sizeKb, lineCount) {
    var card = document.createElement('div');
    card.className = 'long-text-card';
    card.setAttribute('data-msg-id', id);

    var icon = document.createElement('div');
    icon.className = 'card-icon';
    icon.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#999" stroke-width="1.5">'
        + '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        + '<polyline points="14 2 14 8 20 8"/>'
        + '<line x1="16" y1="13" x2="8" y2="13"/>'
        + '<line x1="16" y1="17" x2="8" y2="17"/></svg>';

    var info = document.createElement('div');
    info.className = 'card-info';
    var cardTitle = document.createElement('div');
    cardTitle.className = 'card-title';
    var preview = text.substring(0, 40).replace(/\n/g, ' ');
    if (text.length > 40) preview += '...';
    cardTitle.textContent = preview;
    var cardMeta = document.createElement('div');
    cardMeta.className = 'card-meta';
    cardMeta.textContent = 'TXT · ' + sizeKb + ' KB · ' + lineCount + ' 行';

    info.appendChild(cardTitle);
    info.appendChild(cardMeta);
    card.appendChild(icon);
    card.appendChild(info);
    return card;
}

// ==================== 流式渲染 ====================
function appendReasoning(msgId, token) {
    if (!messageBuffer[msgId]) return;
    messageBuffer[msgId].reasoning += token;
    var wrapper = document.getElementById(msgId);
    if (!wrapper) return;

    var contentDiv = wrapper.querySelector('.message-content');
    var thinkBlock = wrapper.querySelector('.think-block');
    if (!thinkBlock) {
        thinkBlock = document.createElement('details');
        thinkBlock.className = 'think-block';
        thinkBlock.open = true;
        var summary = document.createElement('summary');
        summary.innerText = '深度思考过程...';
        var thinkContent = document.createElement('div');
        thinkContent.className = 'think-content markdown-body';
        thinkBlock.appendChild(summary);
        thinkBlock.appendChild(thinkContent);
        var replyDiv = contentDiv.querySelector('.reply-content');
        contentDiv.insertBefore(thinkBlock, replyDiv);
    }
    wrapper.classList.add('streaming');

    var thinkContent = thinkBlock.querySelector('.think-content');
    thinkContent.innerHTML = '<div class="think-inner">'
        + marked.parse(messageBuffer[msgId].reasoning)
        + '</div>';

    // 🌟 只滚动思考框内部到底部，不动主窗口
    thinkContent.scrollTop = thinkContent.scrollHeight;
}


function appendToken(msgId, token) {
    if (!messageBuffer[msgId]) return;
    messageBuffer[msgId].content += token;
    var wrapper = document.getElementById(msgId);
    if (!wrapper) return;

    wrapper.classList.add('streaming');

    // 🌟 记录滚动状态：在 DOM 重建之前判断
    var shouldFollow = isNearBottom();

    var replyDiv = wrapper.querySelector('.reply-content');
    replyDiv.innerHTML = marked.parse(messageBuffer[msgId].content);
    
    // 🌟 核心修复：用 setTimeout 等待浏览器完成 CSS 应用和布局计算
    setTimeout(function() {
        // 🌟 如果用户本来就在底部附近，自动跟随
        if (shouldFollow) {
            var anchor = document.getElementById('scroll-anchor');
            if (anchor) anchor.scrollIntoView({ behavior: 'auto', block: 'end' });
        }
    }, 0);
}

// app.js
function finishMessage(msgId) {
    var wrapper = document.getElementById(msgId);
    if (!wrapper) { delete messageBuffer[msgId]; return; }

    // --- A. 修复未闭合 Markdown ---
    var content = messageBuffer[msgId].content;
    var codeBlockCount = (content.match(/```/g) || []).length;
    if (codeBlockCount % 2 !== 0) {
        messageBuffer[msgId].content += '\n```';
        var replyDiv = wrapper.querySelector('.reply-content');
        if (replyDiv) {
            replyDiv.innerHTML = marked.parse(messageBuffer[msgId].content);
        }
    }

    // --- B. 对所有折叠代码块：flex-end → scroll 平滑过渡 ---
    // 不再展开任何代码块！
    var collapsedBlocks = wrapper.querySelectorAll('.code-body.collapsed');
    collapsedBlocks.forEach(function(block) {
        // .scroll-locked 的 !important 能覆盖 .streaming 的 flex 布局
        block.classList.add('scroll-locked');
        // 现在是 display:block + overflow:auto，scrollTop 生效
        block.scrollTop = block.scrollHeight;
    });

    // --- C. 移除 streaming ---
    // 此时折叠块靠 .scroll-locked 维持 scroll 模式，不会跳回顶部
    wrapper.classList.remove('streaming');

    // --- D. 折叠思考框 ---
    var thinkBlock = wrapper.querySelector('.think-block');
    if (thinkBlock && thinkBlock.open) {
        thinkBlock.open = false;
        thinkBlock.querySelector('summary').innerText = '已完成深度思考';
    }

    // --- E. 代码高亮 ---
    wrapper.querySelectorAll('pre code').forEach(function(block) {
        try { hljs.highlightElement(block); } catch(e) {}
    });

    // --- F. 等重排完成，移除过渡类，让原生 CSS 接管 ---
    requestAnimationFrame(function() {
        setTimeout(function() {
            collapsedBlocks.forEach(function(block) {
                if (block.classList.contains('collapsed')) {
                    block.classList.remove('scroll-locked');
                    // 移除过渡类后 CSS 回到 overflow-y:auto，再次锁底
                    block.scrollTop = block.scrollHeight;
                }
            });
            var anchor = document.getElementById('scroll-anchor');
            if (anchor) anchor.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }, 50);
    });

    delete messageBuffer[msgId];
}



// ==================== 修复 1：安全的错误注入 ====================
function showError(msgId, errorText) {
    var wrapper = document.getElementById(msgId);
    if (!wrapper) return;
    var contentDiv = wrapper.querySelector('.message-content');
    
    // 防止重复添加标签
    if (contentDiv.querySelector('.system-error')) return;
    
    // 🌟 核心修复：创建一个独立的 DOM 节点，追加在 Markdown 渲染区之外
    // 这样无论 Markdown 内部有没有闭合标签，都不会吞掉我们的错误提示
    var errDiv = document.createElement('div');
    errDiv.className = 'system-error';
    errDiv.innerText = errorText;
    
    contentDiv.appendChild(errDiv);
    softScroll();
}

// ==================== 滚动控制 ====================
// 🌟 只在创建消息等非流式场景使用，温和滚动
function softScroll() {
    var anchor = document.getElementById('scroll-anchor');
    if (anchor) {
        anchor.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
}
// ==================== 历史记录与视图控制 ====================

// 1. 清空整个聊天面板（用于切换左侧会话时）
function clearChat() {
    // 找出所有聊天气泡并移除
    var bubbles = chatContainer.querySelectorAll('.message-wrapper');
    bubbles.forEach(function(b) { b.remove(); });
    
    // 清空内存缓存，防止内存泄漏
    messageBuffer = {};
    longTextStore = {};
    
    // 隐藏欢迎屏幕（因为切换历史记录意味着已经有对话了）
    var welcome = document.querySelector('.welcome-screen');
    if (welcome) welcome.style.display = 'none';
}

// 2. 删除单条消息（附带丝滑的淡出动画）
function deleteMessage(msgId) {
    var wrapper = document.getElementById(msgId);
    if (wrapper) {
        // 加上过渡动画，让气泡优雅地消失
        wrapper.style.transition = "opacity 0.3s ease, transform 0.3s ease";
        wrapper.style.opacity = "0";
        wrapper.style.transform = "translateY(-10px)";
        
        // 动画结束后物理移除 DOM
        setTimeout(function() {
            wrapper.remove();
        }, 300);
    }
    
    // 从缓存中彻底抹除
    delete messageBuffer[msgId];
    delete longTextStore[msgId];
}
// 显示欢迎屏幕（新建空对话时调用）
function showWelcome() {
    var welcome = document.querySelector('.welcome-screen');
    if (welcome) welcome.style.display = 'block';
}

// ==================== 历史记录专用：插入思考块到已存在的气泡 ====================
function insertThinkBlock(msgId, reasoningText) {
    var wrapper = document.getElementById(msgId);
    if (!wrapper) {
        console.error('[JS]: 找不到消息气泡 ' + msgId);
        return;
    }
    
    var contentDiv = wrapper.querySelector('.message-content');
    var replyDiv = contentDiv.querySelector('.reply-content');
    
    // 创建思考块（默认折叠状态）
    var thinkBlock = document.createElement('details');
    thinkBlock.className = 'think-block';
    thinkBlock.open = false;  // 历史记录默认折叠
    
    var summary = document.createElement('summary');
    summary.innerText = '已完成深度思考';
    
    var thinkContent = document.createElement('div');
    thinkContent.className = 'think-content markdown-body';
    thinkContent.innerHTML = '<div class="think-inner">' + marked.parse(reasoningText) + '</div>';
    
    thinkBlock.appendChild(summary);
    thinkBlock.appendChild(thinkContent);
    
    // 插入到回复内容之前
    contentDiv.insertBefore(thinkBlock, replyDiv);
}

// ==================== JS 引擎就绪标志 ====================
// 当所有全局变量和函数都初始化完成后，设置此标志
window.jsReady = true;
console.log('[JS]: 引擎已就绪');