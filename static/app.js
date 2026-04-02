const ordersBody = document.getElementById('orders-body');
const summaryBody = document.getElementById('summary-body');
const statusBox = document.getElementById('status-box');
const orderCount = document.getElementById('order-count');
const summaryCount = document.getElementById('summary-count');
const dbStatus = document.getElementById('db-status');
const lastUpdated = document.getElementById('last-updated');
const manualRefresh = document.getElementById('manual-refresh');

const pollIntervalMs = window.APP_CONFIG?.pollIntervalMs || 5000;
let latestVersion = null;
let isFirstLoad = true;

manualRefresh.addEventListener('click', () => loadDashboard(true));
loadDashboard(true);
setInterval(() => loadDashboard(false), pollIntervalMs);

async function loadDashboard(forceRender) {
    try {
        const response = await fetch(`/api/dashboard-data?ts=${Date.now()}`, {
            cache: 'no-store'
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        const versionChanged = data.last_updated !== latestVersion;

        if (forceRender || isFirstLoad || versionChanged) {
            renderOrders(data.merged_orders || []);
            renderSummary(data.summary || []);
            latestVersion = data.last_updated;
            isFirstLoad = false;
            setStatus(versionChanged && latestVersion ? '检测到数据库变化，页面已自动刷新。' : '数据加载完成。');
        } else {
            setStatus('数据库暂无变化，已完成自动检查。');
        }

        orderCount.textContent = String(data.order_count ?? 0);
        summaryCount.textContent = String(data.summary_count ?? 0);
        dbStatus.textContent = latestVersion ? '已连接' : '未检测到更新时间';
        lastUpdated.textContent = formatDateTime(data.last_updated);
    } catch (error) {
        console.error(error);
        dbStatus.textContent = '连接失败';
        setStatus(`加载失败：${error.message}`);
    }
}

function renderOrders(rows) {
    if (!rows.length) {
        ordersBody.innerHTML = '<tr class="empty-row"><td colspan="7">merged_orders 表中暂无数据。</td></tr>';
        return;
    }

    ordersBody.innerHTML = rows.map(row => `
        <tr>
            <td>${escapeHtml(row.order_id)}</td>
            <td>${escapeHtml(row.customer_id)}</td>
            <td>${escapeHtml(row.customer_name ?? '')}</td>
            <td>${escapeHtml(row.region ?? '')}</td>
            <td>${formatNumber(row.amount)}</td>
            <td>${escapeHtml(row.currency)}</td>
            <td><span class="amount-pill">${formatCurrency(row.amount_cny)}</span></td>
        </tr>
    `).join('');
}

function renderSummary(rows) {
    if (!rows.length) {
        summaryBody.innerHTML = '<tr class="empty-row"><td colspan="2">region_summary 表中暂无数据。</td></tr>';
        return;
    }

    summaryBody.innerHTML = rows.map(row => `
        <tr>
            <td>${escapeHtml(row.region ?? '')}</td>
            <td>${formatCurrency(row.avg_amount_cny)}</td>
        </tr>
    `).join('');
}

function setStatus(message) {
    statusBox.textContent = message;
}

function formatCurrency(value) {
    return new Intl.NumberFormat('zh-CN', {
        style: 'currency',
        currency: 'CNY',
        minimumFractionDigits: 2
    }).format(Number(value) || 0);
}

function formatNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number.toFixed(2) : '--';
}

function formatDateTime(value) {
    if (!value) {
        return '--';
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }

    return date.toLocaleString('zh-CN');
}

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
