"""
Schneider Electric Innovation Sprint - Problem Statement 1
Rule-Based SOP & Tag Knowledge Retrieval Engine using SQLite FTS5 (BM25 Ranking)

Non-Negotiable Rule 4:
Retrieval (SOP/history lookup) is RULE-BASED (SQLite FTS5 / BM25), not a separate LLM call.
"""

import sqlite3
import json
import os
from typing import List, Dict, Any, Optional

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "knowledge_base.db"))
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))

class SOPRetrievalEngine:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create FTS5 virtual table for SOP steps
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS sops_fts USING fts5(
                sop_id,
                title,
                step_num UNINDEXED,
                instruction,
                applies_to_alarms,
                restricted_actions UNINDEXED,
                tokenize='porter unicode61'
            );
        """)

        # Create FTS5 virtual table for Machine Context tags
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS tags_fts USING fts5(
                tag_id,
                raw_address,
                unit_parent,
                description,
                confidence,
                tokenize='porter unicode61'
            );
        """)

        # Check if tables already populated
        cursor.execute("SELECT count(*) FROM sops_fts")
        sop_count = cursor.fetchone()[0]

        if sop_count == 0:
            self._populate_initial_data(cursor)

        conn.commit()
        conn.close()

    def _populate_initial_data(self, cursor: sqlite3.Cursor):
        # 1. Populate SOPs
        sops_file = os.path.join(DATA_DIR, "sops.json")
        if os.path.exists(sops_file):
            with open(sops_file, "r") as f:
                sops = json.load(f)
            for sop in sops:
                sop_id = sop["sop_id"]
                title = sop["title"]
                applies_to = " ".join(sop.get("applies_to_alarms", []))
                restricted = json.dumps(sop.get("restricted_actions", []))
                for s in sop.get("steps", []):
                    cursor.execute("""
                        INSERT INTO sops_fts (sop_id, title, step_num, instruction, applies_to_alarms, restricted_actions)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (sop_id, title, s["step"], s["instruction"], applies_to, restricted))

        # 2. Populate Tags
        mc_file = os.path.join(DATA_DIR, "machine_context.json")
        if os.path.exists(mc_file):
            with open(mc_file, "r") as f:
                mc = json.load(f)
            for tag in mc.get("tags", []):
                cursor.execute("""
                    INSERT INTO tags_fts (tag_id, raw_address, unit_parent, description, confidence)
                    VALUES (?, ?, ?, ?, ?)
                """, (tag["id"], tag.get("raw_address", ""), tag.get("unit_parent", ""), tag.get("description", ""), tag.get("confidence", "high")))

    def lookup_tag_confidence(self, query: str) -> Dict[str, Any]:
        """
        Deterministic check for tag confidence.
        Ambiguous tags like %MW100 must be flagged low-confidence rather than guessed.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Exact check first
        cursor.execute("SELECT tag_id, raw_address, unit_parent, description, confidence FROM tags_fts WHERE tag_id = ? OR raw_address = ?", (query, query))
        row = cursor.fetchone()

        if not row:
            # Try FTS matching
            safe_query = query.replace("%", "").strip()
            if safe_query:
                cursor.execute("SELECT tag_id, raw_address, unit_parent, description, confidence FROM tags_fts WHERE tags_fts MATCH ? LIMIT 1", (f'"{safe_query}"',))
                row = cursor.fetchone()

        conn.close()

        if not row:
            return {
                "match_found": False,
                "confidence_level": "unknown",
                "confidence_score": 0.0,
                "message": f"Tag reference '{query}' not found in verified Machine Context."
            }

        tag_id, raw_addr, parent, desc, conf = row
        if conf == "low":
            return {
                "match_found": True,
                "tag_id": tag_id,
                "raw_address": raw_addr,
                "unit_parent": parent,
                "confidence_level": "low",
                "confidence_score": 0.35,
                "message": f"Ambiguous raw register address ({tag_id}) without verified symbolic binding. Low confidence flag active."
            }

        return {
            "match_found": True,
            "tag_id": tag_id,
            "raw_address": raw_addr,
            "unit_parent": parent,
            "description": desc,
            "confidence_level": "high",
            "confidence_score": 0.95,
            "message": "Verified high-confidence industrial symbol."
        }

    def retrieve_sop_for_cluster(self, alarm_id: str, tag_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Uses FTS5 BM25 ranking to retrieve the most applicable SOP steps for a given alarm event.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # If tag is low confidence, check immediately
        if tag_id:
            tag_conf = self.lookup_tag_confidence(tag_id)
            if tag_conf.get("confidence_level") == "low":
                conn.close()
                return {
                    "matched": False,
                    "confidence_score": 0.35,
                    "confidence_level": "low",
                    "reason": tag_conf["message"],
                    "sop_id": None,
                    "steps": []
                }

        # Step 1: Direct applies_to_alarms exact lookup
        clean_alarm = alarm_id.replace("-", " ")
        query = f'"{alarm_id}"'
        
        cursor.execute("""
            SELECT sop_id, title, step_num, instruction, applies_to_alarms, restricted_actions, bm25(sops_fts) as rank
            FROM sops_fts
            WHERE sops_fts MATCH ?
            ORDER BY rank
            LIMIT 10
        """, (query,))

        rows = cursor.fetchall()

        # If direct alarm match not found, search by tag name or keyword
        if not rows and tag_id:
            tag_clean = tag_id.replace("_", " ")
            cursor.execute("""
                SELECT sop_id, title, step_num, instruction, applies_to_alarms, restricted_actions, bm25(sops_fts) as rank
                FROM sops_fts
                WHERE sops_fts MATCH ?
                ORDER BY rank
                LIMIT 10
            """, (f'"{tag_clean}"',))
            rows = cursor.fetchall()

        conn.close()

        if not rows:
            return {
                "matched": False,
                "confidence_score": 0.20,
                "confidence_level": "none",
                "reason": f"No confident SOP procedure matched for alarm {alarm_id}.",
                "sop_id": None,
                "steps": []
            }

        # Group steps by SOP
        sop_id = rows[0][0]
        sop_title = rows[0][1]
        restricted_actions = json.loads(rows[0][5]) if rows[0][5] else []
        
        steps = []
        for r in rows:
            if r[0] == sop_id:
                steps.append({
                    "step": r[2],
                    "instruction": r[3]
                })

        # Sort steps by step number
        steps = sorted(steps, key=lambda s: s["step"])

        return {
            "matched": True,
            "sop_id": sop_id,
            "sop_title": sop_title,
            "confidence_score": 0.94,
            "confidence_level": "high",
            "restricted_actions": restricted_actions,
            "steps": steps,
            "citation": f"{sop_id}: {sop_title} (Steps 1-{len(steps)})"
        }
