from ingestion.grobid import parse_bibliography, parse_tei, section_chunks


TEI = """
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader>
    <fileDesc>
      <titleStmt><title>Uploaded Study</title></titleStmt>
      <sourceDesc>
        <biblStruct>
          <analytic>
            <title level="a">Uploaded Study</title>
            <author>
              <persName><forename>Ada</forename><surname>Lovelace</surname></persName>
            </author>
            <idno type="DOI">10.1000/uploaded</idno>
          </analytic>
        </biblStruct>
      </sourceDesc>
    </fileDesc>
    <profileDesc>
      <abstract><p>A short abstract.</p></abstract>
    </profileDesc>
  </teiHeader>
  <text>
    <body>
      <div><head>Introduction</head><p>We study graphs.</p></div>
      <div><head>Results</head><p>The method holds.</p></div>
    </body>
    <back>
      <div type="references">
        <listBibl>
          <biblStruct>
            <analytic>
              <title level="a">Attention is all you need</title>
            </analytic>
            <monogr><imprint><date when="2017"/></imprint></monogr>
          </biblStruct>
          <biblStruct>
            <analytic>
              <title level="a">Sentence-BERT</title>
              <idno type="DOI">10.1000/sbert</idno>
            </analytic>
          </biblStruct>
        </listBibl>
      </div>
    </back>
  </text>
</TEI>
"""


def test_grobid_tei_uses_section_boundaries():
    parsed = parse_tei(TEI)
    assert parsed["title"] == "Uploaded Study"
    assert parsed["doi"] == "10.1000/uploaded"
    assert parsed["authors"][0]["name"] == "Ada Lovelace"
    assert [section["section"] for section in parsed["sections"]] == ["Introduction", "Results"]
    chunks = section_chunks("local:1", parsed)
    assert chunks[0]["id"] == "local:1:s1"
    assert "graphs" in chunks[0]["text"]


def test_bibliography_is_kept_so_uploads_have_citation_edges():
    references = parse_bibliography(TEI)
    assert [reference["title"] for reference in references] == [
        "Attention is all you need",
        "Sentence-BERT",
    ]
    assert references[0]["year"] == 2017
    assert references[0]["doi"] is None
    assert references[1]["doi"] == "10.1000/sbert"
