"""
竞品监控路由 — 增强版：支持账号/URL监控 + AI分析 + 结构化快照
"""
import json
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select, func, delete as sql_delete
from core.deps import get_current_user
from core.database import async_session
from models.monitor import MonitorItem, MonitorSnapshot
from loguru import logger

router = APIRouter()


class MonitorCreate(BaseModel):
    name: str = ""
    monitor_type: str = "keyword"  # keyword, account, brand, url
    target: str = ""
    interval_minutes: int = 60
    ai_analysis: bool = False  # 是否启用 AI 分析


@router.get("")
async def list_monitors(user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(select(MonitorItem).order_by(MonitorItem.created_at.desc()))
        items = result.scalars().all()
        return {
            "success": True,
            "data": [
                {"id": m.id, "name": m.name, "monitor_type": m.monitor_type,
                 "target": m.target, "interval_minutes": m.interval_minutes,
                 "is_active": m.is_active, "last_check": str(m.last_check) if m.last_check else None,
                 "created_at": str(m.created_at)} for m in items
            ],
        }


@router.post("")
async def create_monitor(req: MonitorCreate, user=Depends(get_current_user)):
    async with async_session() as db:
        item = MonitorItem(name=req.name, monitor_type=req.monitor_type,
                           target=req.target, interval_minutes=req.interval_minutes)
        db.add(item)
        await db.flush()
        await db.commit()
        return {"success": True, "id": item.id}


@router.delete("/{item_id}")
async def delete_monitor(item_id: int, user=Depends(get_current_user)):
    async with async_session() as db:
        await db.execute(sql_delete(MonitorSnapshot).where(MonitorSnapshot.item_id == item_id))
        await db.execute(sql_delete(MonitorItem).where(MonitorItem.id == item_id))
        await db.commit()
        return {"success": True}


@router.post("/{item_id}/toggle")
async def toggle_monitor(item_id: int, user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(select(MonitorItem).where(MonitorItem.id == item_id))
        item = result.scalar_one_or_none()
        if item:
            item.is_active = not item.is_active
            await db.commit()
        return {"success": True, "is_active": item.is_active if item else False}


@router.get("/{item_id}/snapshots")
async def list_snapshots(item_id: int, limit: int = 50, user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(
            select(MonitorSnapshot).where(MonitorSnapshot.item_id == item_id)
            .order_by(MonitorSnapshot.created_at.desc()).limit(limit)
        )
        snapshots = result.scalars().all()
        return {
            "success": True,
            "data": [
                {"id": s.id, "data_json": s.data_json, "created_at": str(s.created_at)}
                for s in snapshots
            ],
        }


@router.post("/{item_id}/check")
async def check_monitor(item_id: int, user=Depends(get_current_user)):
    """执行监控检查 — 支持关键词/账号/URL三种类型"""
    async with async_session() as db:
        result = await db.execute(select(MonitorItem).where(MonitorItem.id == item_id))
        item = result.scalar_one_or_none()
        if not item:
            return {"success": False, "message": "监控项不存在"}

        t0 = datetime.utcnow()
        snapshot_data = {}

        try:
            from core.config import settings
            from apis.xhs_pc_apis import XHS_Apis
            xhs = XHS_Apis()

            if item.monitor_type == "keyword":
                ok, msg, data = xhs.search_note(item.target, settings.COOKIES)
                if ok:
                    raw_items = data.get("data", {}).get("items", [])[:10]
                    notes = []
                    for it in raw_items:
                        nc = it.get("note_card", {})
                        notes.append({
                            "note_id": it.get("id", ""),
                            "title": nc.get("display_title", ""),
                            "author": nc.get("user", {}).get("nickname", ""),
                            "type": nc.get("type", ""),
                            "likes": nc.get("interact_info", {}).get("liked_count", "0"),
                            "collects": nc.get("interact_info", {}).get("collected_count", "0"),
                            "comments": nc.get("interact_info", {}).get("comment_count", "0"),
                        })
                    snapshot_data = {
                        "type": "keyword",
                        "target": item.target,
                        "count": len(notes),
                        "notes": notes,
                    }
                else:
                    snapshot_data = {"type": "keyword", "target": item.target, "error": msg}

            elif item.monitor_type == "account":
                # 搜索用户笔记
                ok, msg, data = xhs.search_user(item.target, settings.COOKIES)
                if ok:
                    users = []
                    for it in data.get("data", {}).get("items", [])[:5]:
                        ui = it.get("user_info", {})
                        users.append({
                            "user_id": ui.get("user_id", ""),
                            "nickname": ui.get("nickname", ""),
                            "desc": ui.get("desc", "")[:100],
                            "fans": ui.get("fstatus", ""),
                        })
                    snapshot_data = {
                        "type": "account",
                        "target": item.target,
                        "count": len(users),
                        "users": users,
                    }
                else:
                    snapshot_data = {"type": "account", "target": item.target, "error": msg}

            elif item.monitor_type == "url":
                # 从 URL 提取笔记 ID 并获取详情
                note_id = item.target.split("/")[-1].split("?")[0]
                try:
                    note_data = xhs.get_note_by_id(note_id, settings.COOKIES)
                    if note_data and note_data.get("success") is not False:
                        nc = note_data.get("data", {})
                        snapshot_data = {
                            "type": "url",
                            "target": item.target,
                            "note_id": note_id,
                            "title": nc.get("title", ""),
                            "desc": nc.get("desc", "")[:200],
                            "likes": nc.get("interact_info", {}).get("liked_count", "0"),
                            "collects": nc.get("interact_info", {}).get("collected_count", "0"),
                            "comments": nc.get("interact_info", {}).get("comment_count", "0"),
                        }
                    else:
                        snapshot_data = {"type": "url", "target": item.target, "error": "笔记详情获取失败"}
                except Exception as e:
                    snapshot_data = {"type": "url", "target": item.target, "error": str(e)[:100]}

            else:
                snapshot_data = {"type": item.monitor_type, "target": item.target,
                                 "error": f"不支持的监控类型: {item.monitor_type}"}

            # AI 分析（可选）
            try:
                ai_analysis = _analyze_snapshot(snapshot_data)
                if ai_analysis:
                    snapshot_data["ai_analysis"] = ai_analysis
            except Exception as e:
                logger.debug(f"[monitor] AI分析跳过: {e}")

            # 保存快照
            snap = MonitorSnapshot(item_id=item.id, data_json=json.dumps(snapshot_data, ensure_ascii=False))
            db.add(snap)
            item.last_check = datetime.utcnow()
            await db.commit()

            return {"success": True, "data": snapshot_data}
        except Exception as e:
            logger.exception(f"[monitor] Check error: {e}")
            return {"success": False, "message": str(e)[:100]}


def _analyze_snapshot(data: dict) -> dict:
    """对快照数据进行基础统计分析（不依赖 LLM）"""
    analysis = {}

    if data.get("type") == "keyword" and "notes" in data:
        notes = data["notes"]
        if not notes:
            return {}
        # 统计
        likes = [int(n.get("likes", 0) or 0) for n in notes]
        types = {}
        for n in notes:
            t = n.get("type", "normal")
            types[t] = types.get(t, 0) + 1
        analysis = {
            "total_notes": len(notes),
            "avg_likes": round(sum(likes) / len(likes), 1) if likes else 0,
            "max_likes": max(likes) if likes else 0,
            "min_likes": min(likes) if likes else 0,
            "type_distribution": types,
            "top_note": max(notes, key=lambda n: int(n.get("likes", 0) or 0)).get("title", "") if notes else "",
        }
    elif data.get("type") == "account" and "users" in data:
        analysis = {
            "total_users": len(data.get("users", [])),
            "targets_found": data.get("count", 0),
        }
    elif data.get("type") == "url":
        likes = int(data.get("likes", 0) or 0)
        collects = int(data.get("collects", 0) or 0)
        comments = int(data.get("comments", 0) or 0)
        analysis = {
            "engagement_score": likes + collects * 2 + comments * 3,
            "like_collect_ratio": round(likes / max(collects, 1), 2),
            "interaction_level": "高" if likes > 1000 else ("中" if likes > 200 else "低"),
        }

    return analysis


@router.get("/analysis/compare")
async def compare_snapshots(item_id: int, user=Depends(get_current_user)):
    """对比最近两次快照的数据变化"""
    async with async_session() as db:
        result = await db.execute(
            select(MonitorSnapshot).where(MonitorSnapshot.item_id == item_id)
            .order_by(MonitorSnapshot.created_at.desc()).limit(2)
        )
        snapshots = result.scalars().all()

        if len(snapshots) < 2:
            return {"success": True, "data": None, "message": "需要至少两次快照才能对比"}

        try:
            prev = json.loads(snapshots[1].data_json)
            curr = json.loads(snapshots[0].data_json)
        except Exception:
            return {"success": False, "message": "快照数据解析失败"}

        comparison = {
            "prev_time": str(snapshots[1].created_at),
            "curr_time": str(snapshots[0].created_at),
            "type": curr.get("type", "unknown"),
            "changes": {},
        }

        if curr.get("type") == "keyword" and "notes" in curr:
            prev_likes = sum(int(n.get("likes", 0) or 0) for n in prev.get("notes", []))
            curr_likes = sum(int(n.get("likes", 0) or 0) for n in curr.get("notes", []))
            comparison["changes"] = {
                "note_count_change": len(curr.get("notes", [])) - len(prev.get("notes", [])),
                "total_likes_change": curr_likes - prev_likes,
                "new_notes_count": len(set(n.get("note_id") for n in curr.get("notes", []))
                                       - set(n.get("note_id") for n in prev.get("notes", []))),
            }
        elif curr.get("type") == "url":
            comparison["changes"] = {
                "likes_change": int(curr.get("likes", 0) or 0) - int(prev.get("likes", 0) or 0),
                "collects_change": int(curr.get("collects", 0) or 0) - int(prev.get("collects", 0) or 0),
                "comments_change": int(curr.get("comments", 0) or 0) - int(prev.get("comments", 0) or 0),
            }

        return {"success": True, "data": comparison}


@router.delete("/{item_id}/snapshots")
async def clear_snapshots(item_id: int, user=Depends(get_current_user)):
    async with async_session() as db:
        await db.execute(sql_delete(MonitorSnapshot).where(MonitorSnapshot.item_id == item_id))
        await db.commit()
        return {"success": True}
