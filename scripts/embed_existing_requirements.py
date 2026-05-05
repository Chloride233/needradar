"""Batch embed existing vault requirements into ChromaDB.

Usage: python -m scripts.embed_existing_requirements
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from needradar.services.vault_store import vault
from needradar.vector import create_vector_store


async def main():
    vs = create_vector_store()
    all_files = vault.list_files("需求")
    print(f"Found {len(all_files)} requirements in vault")

    batch_size = 50
    total_embedded = 0

    for i in range(0, len(all_files), batch_size):
        batch = all_files[i:i + batch_size]
        ids = []
        documents = []
        metas = []

        for path, meta, body in batch:
            title = meta.get("标题", path.stem)
            # Extract description from body
            desc = ""
            in_desc = False
            for line in body.split("\n"):
                stripped = line.strip()
                if stripped == "## 需求描述":
                    in_desc = True
                    continue
                elif stripped.startswith("## ") and in_desc:
                    break
                elif in_desc and stripped:
                    desc += stripped + " "

            text = f"{title}\n{desc.strip()[:500]}"
            ids.append(title)
            documents.append(text)
            kws = meta.get("关键词", [])
            metas.append({
                "platform": meta.get("来源平台", ""),
                "keyword": ",".join(kws) if isinstance(kws, list) else str(kws),
                "sentiment": meta.get("情感倾向", ""),
                "mentions": str(meta.get("提及次数", 1)),
            })

        try:
            await vs.add(ids=ids, documents=documents, metadatas=metas)
        except Exception as e:
            # Handle duplicate IDs individually
            for id_, doc, m in zip(ids, documents, metas):
                try:
                    await vs.add(ids=[id_], documents=[doc], metadatas=[m])
                except Exception:
                    pass

        total_embedded += len(batch)
        print(f"  Embedded {total_embedded}/{len(all_files)}")

    count = await vs.count()
    print(f"Done. ChromaDB now has {count} documents.")


if __name__ == "__main__":
    asyncio.run(main())
