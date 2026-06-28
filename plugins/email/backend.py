# -*- coding: utf-8 -*-
import glob
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

_logger = logging.getLogger("plugin.email")


def register():
    return [
        {"action": "send_email", "name": "发送邮件"},
    ]


def execute(action, params, context):
    if action in ("send_email", "email_send"):
        return _send_email(params, context)
    return {"ok": False, "error": f"未知动作: {action}"}


def _send_email(params, context):
    smtp_host = params.get("smtp_host", "").strip()
    smtp_port = int(params.get("smtp_port", 465))
    use_ssl = params.get("use_ssl", True)
    username = params.get("username", "").strip()
    password = params.get("password", "").strip()
    to_str = params.get("to", "").strip()
    cc_str = params.get("cc", "").strip()
    subject = params.get("subject", "通知").strip()
    body = params.get("body", "")
    html = params.get("html", False)
    attachments_str = params.get("attachments", "").strip()
    attachment_dir = params.get("attachment_dir", "").strip()
    attachment_pattern = params.get("attachment_pattern", "").strip()

    if not smtp_host:
        return {"ok": False, "error": "SMTP服务器不能为空", "check_results": {"success": False, "error_message": "SMTP服务器不能为空"}}
    if not username:
        return {"ok": False, "error": "发件邮箱不能为空", "check_results": {"success": False, "error_message": "发件邮箱不能为空"}}
    if not password:
        return {"ok": False, "error": "授权码/密码不能为空", "check_results": {"success": False, "error_message": "授权码/密码不能为空"}}
    if not to_str:
        return {"ok": False, "error": "收件人不能为空", "check_results": {"success": False, "error_message": "收件人不能为空"}}

    to_list = [addr.strip() for addr in to_str.split(",") if addr.strip()]
    cc_list = [addr.strip() for addr in cc_str.split(",") if addr.strip()] if cc_str else []

    msg = MIMEMultipart()
    msg["From"] = username
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = subject

    if html:
        msg.attach(MIMEText(body, "html", "utf-8"))
    else:
        msg.attach(MIMEText(body, "plain", "utf-8"))

    all_recipients = to_list + cc_list

    attachment_files = []

    if attachments_str:
        for att_path in attachments_str.split(";"):
            att_path = att_path.strip()
            if not att_path:
                continue
            p = Path(att_path)
            if p.exists() and p.is_file():
                attachment_files.append(p)
            else:
                _logger.warning("[email] 附件不存在: %s", att_path)

    if attachment_dir:
        dir_path = Path(attachment_dir)
        if dir_path.exists() and dir_path.is_dir():
            if attachment_pattern:
                pattern = str(dir_path / attachment_pattern)
                matched = glob.glob(pattern)
                for m in matched:
                    mp = Path(m)
                    if mp.is_file() and mp not in attachment_files:
                        attachment_files.append(mp)
            else:
                for f in sorted(dir_path.iterdir()):
                    if f.is_file() and f not in attachment_files:
                        attachment_files.append(f)

    for att_path in attachment_files:
        try:
            with open(att_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename*=UTF-8''{att_path.name}",
            )
            msg.attach(part)
            _logger.info("[email] 已添加附件: %s", att_path.name)
        except Exception as e:
            _logger.error("[email] 添加附件失败 %s: %s", att_path, e)

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(username, password)
        server.sendmail(username, all_recipients, msg.as_string())
        server.quit()

        context.log("info", f"邮件发送成功: {subject} -> {', '.join(to_list)}")
        _logger.info("[email] 邮件发送成功: %s -> %s", subject, to_list)
        return {"ok": True, "check_results": {"success": True}}
    except smtplib.SMTPAuthenticationError:
        err = "SMTP认证失败，请检查邮箱和授权码"
        context.log("error", err)
        return {"ok": False, "error": err, "check_results": {"success": False, "error_message": err}}
    except smtplib.SMTPException as e:
        err = f"SMTP错误: {e}"
        context.log("error", err)
        return {"ok": False, "error": err, "check_results": {"success": False, "error_message": err}}
    except Exception as e:
        err = f"邮件发送失败: {e}"
        context.log("error", err)
        return {"ok": False, "error": err, "check_results": {"success": False, "error_message": err}}
