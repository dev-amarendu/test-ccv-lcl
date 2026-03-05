"""Data migration script: PostgreSQL -> Firestore.

Prerequisites:
    pip install psycopg2-binary sqlalchemy google-cloud-firestore
    Set env vars:
      POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_HOST
      FIRESTORE_PROJECT_ID, FIRESTORE_DATABASE

Usage:
    python scripts/pg_to_firestore.py
"""

import asyncio
import os
import sys

# Ensure we can import from shared
sys.path.append(os.path.join(os.path.dirname(__file__), "../packages/shared"))

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from google.cloud import firestore
except ImportError:
    print("Error: Missing dependencies. Run: pip install psycopg2-binary google-cloud-firestore")
    sys.exit(1)

from shared.firestore_models import (
    RepoDoc, ScanDoc, FindingDoc, FindingAnalysisDoc, 
    KBFixCardDoc, ScheduleDoc, AuditLogDoc
)
from shared.config import get_settings

settings = get_settings()

PG_DSN = f"postgresql://{os.getenv('POSTGRES_USER', 'ccv_user')}:{os.getenv('POSTGRES_PASSWORD', 'ccv_password')}@{os.getenv('POSTGRES_HOST', 'localhost')}:5432/{os.getenv('POSTGRES_DB', 'ccv')}"


def get_pg_connection():
    return psycopg2.connect(PG_DSN, cursor_factory=RealDictCursor)


def get_firestore_db():
    return firestore.AsyncClient(
        project=settings.firestore_project_id,
        database=settings.firestore_database,
    )


async def migrate_repos(pg_cur, fs_db):
    print("Migrating Repos...")
    pg_cur.execute("SELECT * FROM repos")
    rows = pg_cur.fetchall()
    
    batch = fs_db.batch()
    count = 0
    
    for row in rows:
        doc_id = str(row['id'])
        doc_ref = fs_db.collection("repos").document(doc_id)
        
        repo = RepoDoc(
            id=doc_id,
            org_id=str(row['org_id']),
            name=row['name'],
            default_branch=row['default_branch'],
            connected=row['connected'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )
        batch.set(doc_ref, repo.model_dump(mode="json"))
        count += 1
        
        if count % 400 == 0:
            await batch.commit()
            batch = fs_db.batch()
            print(f"  Committed {count} repos...")
            
    await batch.commit()
    print(f"Total Repos migrated: {count}")


async def migrate_scans(pg_cur, fs_db):
    print("Migrating Scans...")
    pg_cur.execute("SELECT * FROM scans")
    rows = pg_cur.fetchall()
    
    batch = fs_db.batch()
    count = 0
    
    for row in rows:
        doc_id = str(row['id'])
        doc_ref = fs_db.collection("scans").document(doc_id)
        
        # Fetch artifacts for this scan
        # Note: In Firestore, we put artifacts in a subcollection, but here we might just embed or separate
        # The new model puts artifacts in `scans/{scan_id}/artifacts` subcollection
        # We will handle artifacts separately or here?
        # Let's handle artifacts here by querying them
        
        scan = ScanDoc(
            id=doc_id,
            repo_id=str(row['repo_id']),
            commit_sha=row['commit_sha'],
            branch=row['branch'],
            trigger_type=row['trigger_type'],
            status=row['status'],
            external_build_id=row['external_build_id'],
            external_app_id=row['external_app_id'],
            started_at=row['started_at'],
            finished_at=row['finished_at'],
            error_message=row['error_message'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )
        batch.set(doc_ref, scan.model_dump(mode="json"))
        count += 1
        
        if count % 400 == 0:
            await batch.commit()
            batch = fs_db.batch()
            print(f"  Committed {count} scans...")
            
    await batch.commit()
    print(f"Total Scans migrated: {count}")


async def migrate_artifacts(pg_cur, fs_db):
    print("Migrating Artifacts...")
    pg_cur.execute("SELECT * FROM scan_artifacts")
    rows = pg_cur.fetchall()
    
    batch = fs_db.batch()
    count = 0
    
    for row in rows:
        scan_id = str(row['scan_id'])
        doc_id = str(row['id'])
        
        # Subcollection: scans/{scan_id}/artifacts/{artifact_id}
        doc_ref = fs_db.collection("scans").document(scan_id).collection("artifacts").document(doc_id)
        
        # We use a dict here because we might not have a strict model for Artifact in firestore_models.py (Wait, we do: ScanArtifactDoc)
        # But ScanArtifactDoc is embedded? No, `scan_store.py` uses subcollection.
        # Let's just write the dict with correct fields.
        
        artifact_data = {
            "id": doc_id,
            "scan_id": scan_id,
            "artifact_uri": row['artifact_uri'],
            "artifact_sha256": row['artifact_sha256'],
            "build_tool": row['build_tool'],
            "created_at": row['created_at'],
        }
        batch.set(doc_ref, artifact_data)
        count += 1
        
        if count % 400 == 0:
            await batch.commit()
            batch = fs_db.batch()
    
    await batch.commit()
    print(f"Total Artifacts migrated: {count}")


async def migrate_findings(pg_cur, fs_db):
    print("Migrating Findings...")
    pg_cur.execute("SELECT * FROM findings")
    rows = pg_cur.fetchall()
    
    batch = fs_db.batch()
    count = 0
    
    for row in rows:
        doc_id = str(row['id'])
        doc_ref = fs_db.collection("findings").document(doc_id)
        
        finding = FindingDoc(
            id=doc_id,
            scan_id=str(row['scan_id']),
            cwe_id=row['cwe_id'],
            severity=row['severity'],
            title=row['title'],
            file_path=row['file_path'],
            line=row['line'],
            fingerprint=row['fingerprint'],
            enrichment_summary=row['enrichment_summary'],
            enrichment_confidence=row['enrichment_confidence'],
            raw_source_json=row['raw_source_json'],
            code_snippet_json=row['code_snippet_json'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )
        batch.set(doc_ref, finding.model_dump(mode="json"))
        count += 1
        
        if count % 400 == 0:
            await batch.commit()
            batch = fs_db.batch()
            print(f"  Committed {count} findings...")
            
    await batch.commit()
    print(f"Total Findings migrated: {count}")


async def migrate_analyses(pg_cur, fs_db):
    print("Migrating Analyses...")
    pg_cur.execute("SELECT * FROM finding_analyses")
    rows = pg_cur.fetchall()
    
    batch = fs_db.batch()
    count = 0
    
    for row in rows:
        doc_id = str(row['id'])
        doc_ref = fs_db.collection("finding_analyses").document(doc_id)
        
        analysis = FindingAnalysisDoc(
            id=doc_id,
            finding_id=str(row['finding_id']),
            model_name=row['model_name'],
            model_version=row['model_version'],
            root_cause=row['root_cause'],
            risk=row['risk'],
            fix_guidance=row['fix_guidance'],
            references_json=row['references_json'],
            provenance_json=row['provenance_json'],
            confidence=row['confidence'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )
        batch.set(doc_ref, analysis.model_dump(mode="json"))
        count += 1
        
        if count % 400 == 0:
            await batch.commit()
            batch = fs_db.batch()
            
    await batch.commit()
    print(f"Total Analyses migrated: {count}")


async def migrate_kb_cards(pg_cur, fs_db):
    print("Migrating KB Cards...")
    pg_cur.execute("SELECT * FROM kb_fix_cards")
    rows = pg_cur.fetchall()
    
    batch = fs_db.batch()
    count = 0
    
    for row in rows:
        doc_id = str(row['id'])
        doc_ref = fs_db.collection("kb_fix_cards").document(doc_id)
        
        # Postgres had embedding column (vector). We need to convert it to list[float]
        # psycopg2 usually returns a string for vector? Or a list if automatic adapter?
        # pgvector-python adapter registers it. Assuming we get a list or string.
        embedding = row.get('embedding')
        if isinstance(embedding, str):
            # Parse string "[0.1, 0.2, ...]"
            embedding = [float(x) for x in embedding.strip("[]").split(",") if x.strip()]
        
        card = KBFixCardDoc(
            id=doc_id,
            cwe_id=row['cwe_id'],
            title=row['title'],
            tags=row['tags'] or [],
            summary=row['summary'],
            fix_steps_json=row['fix_steps_json'],
            content=row['content'],
            source=row['source'],
            content_hash=row['content_hash'],
            approved=row.get('approved', False), # Might be missing in old schema?
            original_finding_id=str(row['original_finding_id']) if row.get('original_finding_id') else None,
            usage_count=row['usage_count'],
            embedding=embedding,
            embedding_model=row.get('embedding_model'),
            embedding_dim=row.get('embedding_dim'),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )
        batch.set(doc_ref, card.model_dump(mode="json"))
        count += 1
        
        if count % 400 == 0:
            await batch.commit()
            batch = fs_db.batch()
            
    await batch.commit()
    print(f"Total KB Cards migrated: {count}")


async def migrate_schedules(pg_cur, fs_db):
    print("Migrating Schedules...")
    pg_cur.execute("SELECT * FROM scan_schedules")
    rows = pg_cur.fetchall()
    
    batch = fs_db.batch()
    count = 0
    
    for row in rows:
        doc_id = str(row['id'])
        doc_ref = fs_db.collection("schedules").document(doc_id)
        
        schedule = ScheduleDoc(
            id=doc_id,
            repo_id=str(row['repo_id']),
            branch=row['branch'],
            artifact_uri=row['artifact_uri'],
            interval_minutes=row['interval_minutes'],
            enabled=row['enabled'],
            next_run_at=row['next_run_at'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )
        batch.set(doc_ref, schedule.model_dump(mode="json"))
        count += 1
        
        if count % 400 == 0:
            await batch.commit()
            batch = fs_db.batch()
            
    await batch.commit()
    print(f"Total Schedules migrated: {count}")


async def migrate_audit_logs(pg_cur, fs_db):
    print("Migrating Audit Logs...")
    pg_cur.execute("SELECT * FROM audit_logs")
    rows = pg_cur.fetchall()
    
    batch = fs_db.batch()
    count = 0
    
    for row in rows:
        doc_id = str(row['id'])
        doc_ref = fs_db.collection("audit_logs").document(doc_id)
        
        log = AuditLogDoc(
            id=doc_id,
            request_id=row['request_id'],
            actor=row['actor'],
            action=row['action'],
            entity_type=row['entity_type'],
            entity_id=row.get('entity_id'),
            status=row['status'],
            details_json=row['details_json'],
            created_at=row['created_at'],
        )
        batch.set(doc_ref, log.model_dump(mode="json"))
        count += 1
        
        if count % 400 == 0:
            await batch.commit()
            batch = fs_db.batch()
            print(f"  Committed {count} logs...")
            
    await batch.commit()
    print(f"Total Audit Logs migrated: {count}")


async def main():
    try:
        conn = get_pg_connection()
        cur = conn.cursor()
    except Exception as e:
        print(f"Could not connect to Postgres: {e}")
        return

    fs_db = get_firestore_db()

    try:
        await migrate_repos(cur, fs_db)
        await migrate_scans(cur, fs_db)
        await migrate_artifacts(cur, fs_db)
        await migrate_findings(cur, fs_db)
        await migrate_analyses(cur, fs_db)
        await migrate_kb_cards(cur, fs_db)
        await migrate_schedules(cur, fs_db)
        await migrate_audit_logs(cur, fs_db)
        print("Migration completed successfully!")
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    asyncio.run(main())
