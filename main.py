# coding=utf-8

import json
import os
import random
import re
import time
import webbrowser
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr, formatdate, make_msgid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union

import pytz
import requests
import yaml


VERSION = "3.0.5"


# === SMTP邮件配置 ===
SMTP_CONFIGS = {
    # Gmail（使用 STARTTLS）
    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "encryption": "TLS"},
    # QQ邮箱（使用 SSL，更稳定）
    "qq.com": {"server": "smtp.qq.com", "port": 465, "encryption": "SSL"},
    # Outlook（使用 STARTTLS）
    "outlook.com": {
        "server": "smtp-mail.outlook.com",
        "port": 587,
        "encryption": "TLS",
    },
    "hotmail.com": {
        "server": "smtp-mail.outlook.com",
        "port": 587,
        "encryption": "TLS",
    },
    "live.com": {"server": "smtp-mail.outlook.com", "port": 587, "encryption": "TLS"},
    # 网易邮箱（使用 SSL，更稳定）
    "163.com": {"server": "smtp.163.com", "port": 465, "encryption": "SSL"},
    "126.com": {"server": "smtp.126.com", "port": 465, "encryption": "SSL"},
    # 新浪邮箱（使用 SSL）
    "sina.com": {"server": "smtp.sina.com", "port": 465, "encryption": "SSL"},
    # 搜狐邮箱（使用 SSL）
    "sohu.com": {"server": "smtp.sohu.com", "port": 465, "encryption": "SSL"},
}


# === 配置管理 ===
def load_config():
    """加载配置文件"""
    config_path = os.environ.get("CONFIG_PATH", "config/config.yaml")

    if not Path(config_path).exists():
        raise FileNotFoundError(f"配置文件 {config_path} 不存在")

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    print(f"配置文件加载成功: {config_path}")

    # 构建配置
    config = {
        "VERSION_CHECK_URL": config_data["app"]["version_check_url"],
        "SHOW_VERSION_UPDATE": config_data["app"]["show_version_update"],
        "REQUEST_INTERVAL": config_data["crawler"]["request_interval"],
        "REPORT_MODE": os.environ.get("REPORT_MODE", "").strip()
        or config_data["report"]["mode"],
        "RANK_THRESHOLD": config_data["report"]["rank_threshold"],
        "USE_PROXY": config_data["crawler"]["use_proxy"],
        "DEFAULT_PROXY": config_data["crawler"]["default_proxy"],
        "ENABLE_CRAWLER": os.environ.get("ENABLE_CRAWLER", "").strip().lower()
        in ("true", "1")
        if os.environ.get("ENABLE_CRAWLER", "").strip()
        else config_data["crawler"]["enable_crawler"],
        "ENABLE_NOTIFICATION": os.environ.get("ENABLE_NOTIFICATION", "").strip().lower()
        in ("true", "1")
        if os.environ.get("ENABLE_NOTIFICATION", "").strip()
        else config_data["notification"]["enable_notification"],
        "MESSAGE_BATCH_SIZE": config_data["notification"]["message_batch_size"],
        "DINGTALK_BATCH_SIZE": config_data["notification"].get(
            "dingtalk_batch_size", 20000
        ),
        "FEISHU_BATCH_SIZE": config_data["notification"].get("feishu_batch_size", 29000),
        "BATCH_SEND_INTERVAL": config_data["notification"]["batch_send_interval"],
        "FEISHU_MESSAGE_SEPARATOR": config_data["notification"][
            "feishu_message_separator"
        ],
        "PUSH_WINDOW": {
            "ENABLED": os.environ.get("PUSH_WINDOW_ENABLED", "").strip().lower()
            in ("true", "1")
            if os.environ.get("PUSH_WINDOW_ENABLED", "").strip()
            else config_data["notification"]
            .get("push_window", {})
            .get("enabled", False),
            "TIME_RANGE": {
                "START": os.environ.get("PUSH_WINDOW_START", "").strip()
                or config_data["notification"]
                .get("push_window", {})
                .get("time_range", {})
                .get("start", "08:00"),
                "END": os.environ.get("PUSH_WINDOW_END", "").strip()
                or config_data["notification"]
                .get("push_window", {})
                .get("time_range", {})
                .get("end", "22:00"),
            },
            "ONCE_PER_DAY": os.environ.get("PUSH_WINDOW_ONCE_PER_DAY", "").strip().lower()
            in ("true", "1")
            if os.environ.get("PUSH_WINDOW_ONCE_PER_DAY", "").strip()
            else config_data["notification"]
            .get("push_window", {})
            .get("once_per_day", True),
            "RECORD_RETENTION_DAYS": int(
                os.environ.get("PUSH_WINDOW_RETENTION_DAYS", "").strip() or "0"
            )
            or config_data["notification"]
            .get("push_window", {})
            .get("push_record_retention_days", 7),
        },
        "WEIGHT_CONFIG": {
            "RANK_WEIGHT": config_data["weight"]["rank_weight"],
            "FREQUENCY_WEIGHT": config_data["weight"]["frequency_weight"],
            "HOTNESS_WEIGHT": config_data["weight"]["hotness_weight"],
        },
        "PLATFORMS": config_data["platforms"],
    }

    # 通知渠道配置（环境变量优先）
    notification = config_data.get("notification", {})
    webhooks = notification.get("webhooks", {})

    config["FEISHU_WEBHOOK_URL"] = os.environ.get(
        "FEISHU_WEBHOOK_URL", ""
    ).strip() or webhooks.get("feishu_url", "")
    config["DINGTALK_WEBHOOK_URL"] = os.environ.get(
        "DINGTALK_WEBHOOK_URL", ""
    ).strip() or webhooks.get("dingtalk_url", "")
    config["WEWORK_WEBHOOK_URL"] = os.environ.get(
        "WEWORK_WEBHOOK_URL", ""
    ).strip() or webhooks.get("wework_url", "")
    config["TELEGRAM_BOT_TOKEN"] = os.environ.get(
        "TELEGRAM_BOT_TOKEN", ""
    ).strip() or webhooks.get("telegram_bot_token", "")
    config["TELEGRAM_CHAT_ID"] = os.environ.get(
        "TELEGRAM_CHAT_ID", ""
    ).strip() or webhooks.get("telegram_chat_id", "")

    # 邮件配置
    config["EMAIL_FROM"] = os.environ.get("EMAIL_FROM", "").strip() or webhooks.get(
        "email_from", ""
    )
    config["EMAIL_PASSWORD"] = os.environ.get(
        "EMAIL_PASSWORD", ""
    ).strip() or webhooks.get("email_password", "")
    config["EMAIL_TO"] = os.environ.get("EMAIL_TO", "").strip() or webhooks.get(
        "email_to", ""
    )
    config["EMAIL_SMTP_SERVER"] = os.environ.get(
        "EMAIL_SMTP_SERVER", ""
    ).strip() or webhooks.get("email_smtp_server", "")
    config["EMAIL_SMTP_PORT"] = os.environ.get(
        "EMAIL_SMTP_PORT", ""
    ).strip() or webhooks.get("email_smtp_port", "")

    # ntfy配置
    config["NTFY_SERVER_URL"] = os.environ.get(
        "NTFY_SERVER_URL", "https://ntfy.sh"
    ).strip() or webhooks.get("ntfy_server_url", "https://ntfy.sh")
    config["NTFY_TOPIC"] = os.environ.get("NTFY_TOPIC", "").strip() or webhooks.get(
        "ntfy_topic", ""
    )
    config["NTFY_TOKEN"] = os.environ.get("NTFY_TOKEN", "").strip() or webhooks.get(
        "ntfy_token", ""
    )

    # 输出配置来源信息
    notification_sources = []
    if config["FEISHU_WEBHOOK_URL"]:
        source = "环境变量" if os.environ.get("FEISHU_WEBHOOK_URL") else "配置文件"
        notification_sources.append(f"飞书({source})")
    if config["DINGTALK_WEBHOOK_URL"]:
        source = "环境变量" if os.environ.get("DINGTALK_WEBHOOK_URL") else "配置文件"
        notification_sources.append(f"钉钉({source})")
    if config["WEWORK_WEBHOOK_URL"]:
        source = "环境变量" if os.environ.get("WEWORK_WEBHOOK_URL") else "配置文件"
        notification_sources.append(f"企业微信({source})")
    if config["TELEGRAM_BOT_TOKEN"] and config["TELEGRAM_CHAT_ID"]:
        token_source = (
            "环境变量" if os.environ.get("TELEGRAM_BOT_TOKEN") else "配置文件"
        )
        chat_source = "环境变量" if os.environ.get("TELEGRAM_CHAT_ID") else "配置文件"
        notification_sources.append(f"Telegram({token_source}/{chat_source})")
    if config["EMAIL_FROM"] and config["EMAIL_PASSWORD"] and config["EMAIL_TO"]:
        from_source = "环境变量" if os.environ.get("EMAIL_FROM") else "配置文件"
        notification_sources.append(f"邮件({from_source})")

    if config["NTFY_SERVER_URL"] and config["NTFY_TOPIC"]:
        server_source = "环境变量" if os.environ.get("NTFY_SERVER_URL") else "配置文件"
        notification_sources.append(f"ntfy({server_source})")

    if notification_sources:
        print(f"通知渠道配置来源: {', '.join(notification_sources)}")
    else:
        print("未配置任何通知渠道")

    return config


print("正在加载配置...")
CONFIG = load_config()
print(f"TrendRadar v{VERSION} 配置加载完成")
print(f"监控平台数量: {len(CONFIG['PLATFORMS'])}")


# === 工具函数 ===
def get_beijing_time():
    """获取北京时间"""
    return datetime.now(pytz.timezone("Asia/Shanghai"))


def format_date_folder():
    """格式化日期文件夹"""
    return get_beijing_time().strftime("%Y年%m月%d日")


def format_time_filename():
    """格式化时间文件名"""
    return get_beijing_time().strftime("%H时%M分")


def clean_title(title: str) -> str:
    """清理标题中的特殊字符"""
    if not isinstance(title, str):
        title = str(title)
    cleaned_title = title.replace("\n", " ").replace("\r", " ")
    cleaned_title = re.sub(r"\s+", " ", cleaned_title)
    cleaned_title = cleaned_title.strip()
    return cleaned_title


def ensure_directory_exists(directory: str):
    """确保目录存在"""
    Path(directory).mkdir(parents=True, exist_ok=True)


def get_output_path(subfolder: str, filename: str) -> str:
    """获取输出路径"""
    date_folder = format_date_folder()
    output_dir = Path("output") / date_folder / subfolder
    ensure_directory_exists(str(output_dir))
    return str(output_dir / filename)


def check_version_update(
    current_version: str, version_url: str, proxy_url: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """检查版本更新"""
    try:
        proxies = None
        if proxy_url:
            proxies = {"http": proxy_url, "https": proxy_url}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/plain, */*",
            "Cache-Control": "no-cache",
        }

        response = requests.get(
            version_url, proxies=proxies, headers=headers, timeout=10
        )
        response.raise_for_status()

        remote_version = response.text.strip()
        print(f"当前版本: {current_version}, 远程版本: {remote_version}")

        # 比较版本
        def parse_version(version_str):
            try:
                parts = version_str.strip().split(".")
                if len(parts) != 3:
                    raise ValueError("版本号格式不正确")
                return int(parts[0]), int(parts[1]), int(parts[2])
            except:
                return 0, 0, 0

        current_tuple = parse_version(current_version)
        remote_tuple = parse_version(remote_version)

        need_update = current_tuple < remote_tuple
        return need_update, remote_version if need_update else None

    except Exception as e:
        print(f"版本检查失败: {e}")
        return False, None


def is_first_crawl_today() -> bool:
    """检测是否是当天第一次爬取"""
    date_folder = format_date_folder()
    txt_dir = Path("output") / date_folder / "txt"

    if not txt_dir.exists():
        return True

    files = sorted([f for f in txt_dir.iterdir() if f.suffix == ".txt"])
    return len(files) <= 1


def html_escape(text: str) -> str:
    """HTML转义"""
    if not isinstance(text, str):
        text = str(text)

    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


# === 推送记录管理 ===
class PushRecordManager:
    """推送记录管理器"""

    def __init__(self):
        self.record_dir = Path("output") / ".push_records"
        self.ensure_record_dir()
        self.cleanup_old_records()

    def ensure_record_dir(self):
        """确保记录目录存在"""
        self.record_dir.mkdir(parents=True, exist_ok=True)

    def get_today_record_file(self) -> Path:
        """获取今天的记录文件路径"""
        today = get_beijing_time().strftime("%Y%m%d")
        return self.record_dir / f"push_record_{today}.json"

    def cleanup_old_records(self):
        """清理过期的推送记录"""
        retention_days = CONFIG["PUSH_WINDOW"]["RECORD_RETENTION_DAYS"]
        current_time = get_beijing_time()

        for record_file in self.record_dir.glob("push_record_*.json"):
            try:
                date_str = record_file.stem.replace("push_record_", "")
                file_date = datetime.strptime(date_str, "%Y%m%d")
                file_date = pytz.timezone("Asia/Shanghai").localize(file_date)

                if (current_time - file_date).days > retention_days:
                    record_file.unlink()
                    print(f"清理过期推送记录: {record_file.name}")
            except Exception as e:
                print(f"清理记录文件失败 {record_file}: {e}")

    def has_pushed_today(self) -> bool:
        """检查今天是否已经推送过"""
        record_file = self.get_today_record_file()

        if not record_file.exists():
            return False

        try:
            with open(record_file, "r", encoding="utf-8") as f:
                record = json.load(f)
            return record.get("pushed", False)
        except Exception as e:
            print(f"读取推送记录失败: {e}")
            return False

    def record_push(self, report_type: str):
        """记录推送"""
        record_file = self.get_today_record_file()
        now = get_beijing_time()

        record = {
            "pushed": True,
            "push_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "report_type": report_type,
        }

        try:
            with open(record_file, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
            print(f"推送记录已保存: {report_type} at {now.strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"保存推送记录失败: {e}")

    def is_in_time_range(self, start_time: str, end_time: str) -> bool:
        """检查当前时间是否在指定时间范围内"""
        now = get_beijing_time()
        current_time = now.strftime("%H:%M")
    
        def normalize_time(time_str: str) -> str:
            """将时间字符串标准化为 HH:MM 格式"""
            try:
                parts = time_str.strip().split(":")
                if len(parts) != 2:
                    raise ValueError(f"时间格式错误: {time_str}")
            
                hour = int(parts[0])
                minute = int(parts[1])
            
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError(f"时间范围错误: {time_str}")
            
                return f"{hour:02d}:{minute:02d}"
            except Exception as e:
                print(f"时间格式化错误 '{time_str}': {e}")
                return time_str
    
        normalized_start = normalize_time(start_time)
        normalized_end = normalize_time(end_time)
        normalized_current = normalize_time(current_time)
    
        result = normalized_start <= normalized_current <= normalized_end
    
        if not result:
            print(f"时间窗口判断：当前 {normalized_current}，窗口 {normalized_start}-{normalized_end}")
    
        return result


# === 数据获取 ===
class DataFetcher:
    """数据获取器"""

    def __init__(self, proxy_url: Optional[str] = None):
        self.proxy_url = proxy_url

    def fetch_data(
        self,
        id_info: Union[str, Tuple[str, str]],
        max_retries: int = 2,
        min_retry_wait: int = 3,
        max_retry_wait: int = 5,
    ) -> Tuple[Optional[str], str, str]:
        """获取指定ID数据，支持重试"""
        if isinstance(id_info, tuple):
            id_value, alias = id_info
        else:
            id_value = id_info
            alias = id_value

        url = f"https://newsnow.busiyi.world/api/s?id={id_value}&latest"

        proxies = None
        if self.proxy_url:
            proxies = {"http": self.proxy_url, "https": self.proxy_url}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }

        retries = 0
        while retries <= max_retries:
            try:
                response = requests.get(
                    url, proxies=proxies, headers=headers, timeout=10
                )
                response.raise_for_status()

                data_text = response.text
                data_json = json.loads(data_text)

                status = data_json.get("status", "未知")
                if status not in ["success", "cache"]:
                    raise ValueError(f"响应状态异常: {status}")

                status_info = "最新数据" if status == "success" else "缓存数据"
                print(f"获取 {id_value} 成功（{status_info}）")
                return data_text, id_value, alias

            except Exception as e:
                retries += 1
                if retries <= max_retries:
                    base_wait = random.uniform(min_retry_wait, max_retry_wait)
                    additional_wait = (retries - 1) * random.uniform(1, 2)
                    wait_time = base_wait + additional_wait
                    print(f"请求 {id_value} 失败: {e}. {wait_time:.2f}秒后重试...")
                    time.sleep(wait_time)
                else:
                    print(f"请求 {id_value} 失败: {e}")
                    return None, id_value, alias
        return None, id_value, alias

    def fetch_search_data(
        self,
        platform_id: str,
        keywords: List[str],
        max_retries: int = 2,
        min_retry_wait: int = 3,
        max_retry_wait: int = 5,
    ) -> Tuple[Optional[str], str, str]:
        """获取平台搜索数据"""
        # 构建搜索URL
        search_queries = " OR ".join([f'"{keyword}"' for keyword in keywords])
        
        # 不同平台的搜索API端点
        search_endpoints = {
            "toutiao": f"https://newsnow.busiyi.world/api/s?id={platform_id}&search={search_queries}",
            "baidu": f"https://newsnow.busiyi.world/api/s?id={platform_id}&search={search_queries}",
            "weibo": f"https://newsnow.busiyi.world/api/s?id={platform_id}&search={search_queries}",
            "zhihu": f"https://newsnow.busiyi.world/api/s?id={platform_id}&search={search_queries}",
            "bilibili-hot-search": f"https://newsnow.busiyi.world/api/s?id={platform_id}&search={search_queries}",
            "thepaper": f"https://newsnow.busiyi.world/api/s?id={platform_id}&search={search_queries}",
            "ifeng": f"https://newsnow.busiyi.world/api/s?id={platform_id}&search={search_queries}",
            "tieba": f"https://newsnow.busiyi.world/api/s?id={platform_id}&search={search_queries}",
            "douyin": f"https://newsnow.busiyi.world/api/s?id={platform_id}&search={search_queries}",
        }
        
        url = search_endpoints.get(platform_id, f"https://newsnow.busiyi.world/api/s?id={platform_id}&search={search_queries}")

        proxies = None
        if self.proxy_url:
            proxies = {"http": self.proxy_url, "https": self.proxy_url}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }

        retries = 0
        while retries <= max_retries:
            try:
                response = requests.get(
                    url, proxies=proxies, headers=headers, timeout=15
                )
                response.raise_for_status()

                data_text = response.text
                data_json = json.loads(data_text)

                status = data_json.get("status", "未知")
                if status not in ["success", "cache"]:
                    raise ValueError(f"响应状态异常: {status}")

                status_info = "最新数据" if status == "success" else "缓存数据"
                print(f"获取 {platform_id} 搜索数据成功（{status_info}）关键词: {keywords}")
                return data_text, platform_id, " | ".join(keywords)

            except Exception as e:
                retries += 1
                if retries <= max_retries:
                    base_wait = random.uniform(min_retry_wait, max_retry_wait)
                    additional_wait = (retries - 1) * random.uniform(1, 2)
                    wait_time = base_wait + additional_wait
                    print(f"请求 {platform_id} 搜索失败: {e}. {wait_time:.2f}秒后重试...")
                    time.sleep(wait_time)
                else:
                    print(f"请求 {platform_id} 搜索失败: {e}")
                    return None, platform_id, " | ".join(keywords)
        return None, platform_id, " | ".join(keywords)

    def _calculate_match_score(self, title: str, content: str, keywords: List[str]) -> float:
        """计算内容与关键词的匹配度"""
        if not title and not content:
            return 0.0
            
        text = (title + " " + content).lower()
        total_keywords = len(keywords)
        matched_keywords = 0
        
        for keyword in keywords:
            if keyword.lower() in text:
                matched_keywords += 1
                
        return matched_keywords / total_keywords if total_keywords > 0 else 0.0

    def crawl_platforms_with_search(
        self,
        platforms_config: List[Dict],
        request_interval: int = CONFIG["REQUEST_INTERVAL"],
    ) -> Tuple[Dict, Dict, List]:
        """爬取多个平台数据，支持热搜榜和搜索功能"""
        results = {}
        id_to_name = {}
        failed_ids = []

        for i, platform in enumerate(platforms_config):
            platform_id = platform["id"]
            platform_name = platform.get("name", platform_id)
            
            id_to_name[platform_id] = platform_name

            # 检查是否启用搜索功能
            search_enabled = platform.get("search_enabled", False)
            search_keywords = platform.get("search_keywords", [])

            if search_enabled and search_keywords:
                # 执行搜索功能
                print(f"正在搜索 {platform_name} 的关键词: {search_keywords}")
                response, _, search_alias = self.fetch_search_data(
                    platform_id, search_keywords
                )
                
                if response:
                    try:
                        data = json.loads(response)
                        results[platform_id] = {}
                        
                        # 处理搜索结果
                        for index, item in enumerate(data.get("items", []), 1):
                            title = item["title"]
                            url = item.get("url", "")
                            mobile_url = item.get("mobileUrl", "")
                            content = item.get("content", "")  # 获取内容
                            publish_time = item.get("publishTime", "")  # 获取发布时间
                            author = item.get("author", "")  # 获取作者

                            # 构建更丰富的信息
                            full_info = {
                                "ranks": [index],
                                "url": url,
                                "mobileUrl": mobile_url,
                                "content": content,
                                "publishTime": publish_time,
                                "author": author,
                                "searchKeywords": search_keywords,
                                "searchMatch": self._calculate_match_score(title, content, search_keywords)
                            }
                            
                            if title in results[platform_id]:
                                results[platform_id][title]["ranks"].append(index)
                            else:
                                results[platform_id][title] = full_info
                                
                    except json.JSONDecodeError:
                        print(f"解析 {platform_id} 搜索响应失败")
                        failed_ids.append(f"{platform_id}_search")
                    except Exception as e:
                        print(f"处理 {platform_id} 搜索数据出错: {e}")
                        failed_ids.append(f"{platform_id}_search")
                else:
                    failed_ids.append(f"{platform_id}_search")
            else:
                # 执行原有的热搜榜功能
                print(f"正在获取 {platform_name} 的热搜榜")
                response, _, _ = self.fetch_data((platform_id, platform_name))
                
                if response:
                    try:
                        data = json.loads(response)
                        results[platform_id] = {}
                        for index, item in enumerate(data.get("items", []), 1):
                            title = item["title"]
                            url = item.get("url", "")
                            mobile_url = item.get("mobileUrl", "")

                            if title in results[platform_id]:
                                results[platform_id][title]["ranks"].append(index)
                            else:
                                results[platform_id][title] = {
                                    "ranks": [index],
                                    "url": url,
                                    "mobileUrl": mobile_url,
                                    "content": "",  # 热搜榜没有详细内容
                                    "publishTime": "",
                                    "author": "",
                                    "searchKeywords": [],
                                    "searchMatch": 0
                                }
                    except Exception as e:
                        print(f"处理 {platform_id} 热搜数据出错: {e}")
                        failed_ids.append(platform_id)
                else:
                    failed_ids.append(platform_id)

            # 请求间隔
            if i < len(platforms_config) - 1:
                actual_interval = request_interval + random.randint(-10, 20)
                actual_interval = max(50, actual_interval)
                time.sleep(actual_interval / 1000)

        print(f"成功: {list(results.keys())}, 失败: {failed_ids}")
        return results, id_to_name, failed_ids

    def crawl_websites(
        self,
        ids_list: List[Union[str, Tuple[str, str]]],
        request_interval: int = CONFIG["REQUEST_INTERVAL"],
    ) -> Tuple[Dict, Dict, List]:
        """爬取多个网站数据（兼容旧版本）"""
        results = {}
        id_to_name = {}
        failed_ids = []

        for i, id_info in enumerate(ids_list):
            if isinstance(id_info, tuple):
                id_value, name = id_info
            else:
                id_value = id_info
                name = id_value

            id_to_name[id_value] = name
            response, _, _ = self.fetch_data(id_info)

            if response:
                try:
                    data = json.loads(response)
                    results[id_value] = {}
                    for index, item in enumerate(data.get("items", []), 1):
                        title = item["title"]
                        url = item.get("url", "")
                        mobile_url = item.get("mobileUrl", "")

                        if title in results[id_value]:
                            results[id_value][title]["ranks"].append(index)
                        else:
                            results[id_value][title] = {
                                "ranks": [index],
                                "url": url,
                                "mobileUrl": mobile_url,
                                "content": "",
                                "publishTime": "",
                                "author": "",
                                "searchKeywords": [],
                                "searchMatch": 0
                            }
                except json.JSONDecodeError:
                    print(f"解析 {id_value} 响应失败")
                    failed_ids.append(id_value)
                except Exception as e:
                    print(f"处理 {id_value} 数据出错: {e}")
                    failed_ids.append(id_value)
            else:
                failed_ids.append(id_value)

            if i < len(ids_list) - 1:
                actual_interval = request_interval + random.randint(-10, 20)
                actual_interval = max(50, actual_interval)
                time.sleep(actual_interval / 1000)

        print(f"成功: {list(results.keys())}, 失败: {failed_ids}")
        return results, id_to_name, failed_ids


# === 数据处理 ===
def save_titles_to_file(results: Dict, id_to_name: Dict, failed_ids: List) -> str:
    """保存标题到文件，包含搜索信息"""
    file_path = get_output_path("txt", f"{format_time_filename()}.txt")

    with open(file_path, "w", encoding="utf-8") as f:
        for id_value, title_data in results.items():
            name = id_to_name.get(id_value)
            if name and name != id_value:
                f.write(f"{id_value} | {name}\n")
            else:
                f.write(f"{id_value}\n")

            # 按匹配度排序标题
            sorted_titles = []
            for title, info in title_data.items():
                cleaned_title = clean_title(title)
                ranks = info.get("ranks", [])
                url = info.get("url", "")
                mobile_url = info.get("mobileUrl", "")
                content = info.get("content", "")
                publish_time = info.get("publishTime", "")
                author = info.get("author", "")
                search_keywords = info.get("searchKeywords", [])
                match_score = info.get("searchMatch", 0)

                rank = ranks[0] if ranks else 1
                sorted_titles.append((match_score, rank, cleaned_title, url, mobile_url, 
                                    content, publish_time, author, search_keywords))

            # 按匹配度降序排序
            sorted_titles.sort(key=lambda x: (-x[0], x[1]))

            for match_score, rank, cleaned_title, url, mobile_url, content, publish_time, author, search_keywords in sorted_titles:
                line = f"{rank}. {cleaned_title}"
                
                # 添加匹配度信息
                if match_score > 0:
                    line += f" [匹配度:{match_score:.2f}]"
                
                if url:
                    line += f" [URL:{url}]"
                if mobile_url:
                    line += f" [MOBILE:{mobile_url}]"
                if content:
                    # 截取内容前100字符
                    content_preview = content[:100] + "..." if len(content) > 100 else content
                    line += f" [CONTENT:{content_preview}]"
                if publish_time:
                    line += f" [TIME:{publish_time}]"
                if author:
                    line += f" [AUTHOR:{author}]"
                if search_keywords:
                    line += f" [KEYWORDS:{','.join(search_keywords)}]"
                    
                f.write(line + "\n")

            f.write("\n")

        if failed_ids:
            f.write("==== 以下ID请求失败 ====\n")
            for id_value in failed_ids:
                f.write(f"{id_value}\n")

    return file_path


def load_frequency_words(
    frequency_file: Optional[str] = None,
) -> Tuple[List[Dict], List[str]]:
    """加载频率词配置"""
    if frequency_file is None:
        frequency_file = os.environ.get(
            "FREQUENCY_WORDS_PATH", "config/frequency_words.txt"
        )

    frequency_path = Path(frequency_file)
    if not frequency_path.exists():
        raise FileNotFoundError(f"频率词文件 {frequency_file} 不存在")

    with open(frequency_path, "r", encoding="utf-8") as f:
        content = f.read()

    word_groups = [group.strip() for group in content.split("\n\n") if group.strip()]

    processed_groups = []
    filter_words = []

    for group in word_groups:
        words = [word.strip() for word in group.split("\n") if word.strip()]

        group_required_words = []
        group_normal_words = []
        group_filter_words = []

        for word in words:
            if word.startswith("!"):
                filter_words.append(word[1:])
                group_filter_words.append(word[1:])
            elif word.startswith("+"):
                group_required_words.append(word[1:])
            else:
                group_normal_words.append(word)

        if group_required_words or group_normal_words:
            if group_normal_words:
                group_key = " ".join(group_normal_words)
            else:
                group_key = " ".join(group_required_words)

            processed_groups.append(
                {
                    "required": group_required_words,
                    "normal": group_normal_words,
                    "group_key": group_key,
                }
            )

    return processed_groups, filter_words


def parse_file_titles(file_path: Path) -> Tuple[Dict, Dict]:
    """解析单个txt文件的标题数据，返回(titles_by_id, id_to_name)"""
    titles_by_id = {}
    id_to_name = {}

    with open(file_path, "r", encoding="
