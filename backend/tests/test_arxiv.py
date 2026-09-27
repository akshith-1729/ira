from ingestion.arxiv import parse_arxiv_atom


ATOM = """
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v1</id>
    <title>Attention Is All You Need</title>
    <summary>We propose a new network architecture.</summary>
    <published>2017-06-12T00:00:00Z</published>
    <author><name>Ashish Vaswani</name></author>
    <arxiv:doi>10.5555/3295222</arxiv:doi>
  </entry>
</feed>
"""


def test_arxiv_atom_parse():
    meta = parse_arxiv_atom(ATOM)
    assert meta["title"] == "Attention Is All You Need"
    assert meta["year"] == 2017
    assert meta["doi"] == "10.5555/3295222"
    assert meta["arxiv_id"] == "1706.03762"
    assert meta["authors"][0]["name"] == "Ashish Vaswani"
