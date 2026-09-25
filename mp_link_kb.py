"""Attach KB 'zist' (+ its two documents) as Mastery Path topic sources."""
import sys
from pathlib import Path
from deeptutor.learning.storage import LearningStore
from deeptutor.learning.models import TopicSource, TopicSourceKind, TopicMetadata
path = sys.argv[1] if len(sys.argv) > 1 else "zist"
s = LearningStore(Path(__file__).resolve().parent / "study" / "mastery")
t = s.get_topic(path)
meta = t.metadata if t else TopicMetadata(path_id=path, goal="زیست ۱، ۲، ۳ کنکور")
src = [x for x in (t.sources if t else []) if x.source_id != "zist" and not x.metadata.get("kb_name")]
src += [
  TopicSource(id="kb-zist", kind=TopicSourceKind.KNOWLEDGE_BASE, source_id="zist", label="پایگاه دانش زیست (LightRAG)"),
  TopicSource(id="file-jozve", kind=TopicSourceKind.FILE, source_id="jozve_nokte_test_zist.pdf", label="جزوهٔ نکته و تست زیست سنجش", metadata={"kb_name": "zist"}),
  TopicSource(id="file-booklet", kind=TopicSourceKind.FILE, source_id="konkur1405_zist_booklet.md", label="دفترچهٔ زیست کنکور ۱۴۰۵", metadata={"kb_name": "zist"}),
]
t = s.put_topic(meta, src)
print(path, [(x.kind.value, x.source_id) for x in t.sources])
