
import rdflib
import urllib.error
import urllib.request
from typing import Any, Dict
from html.parser import HTMLParser
from rdflib.namespace import RDF, DC, FOAF, RDFS
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.a3.domain.port.document import DocumentKnowledgeGraphPort
from ontobdc.shared.domain.resource.capability import QueryCapability, CapabilityMetadata


class ExtractTransformPublicWebLinkCapability(QueryCapability):
    """
    Capability to fetch a web link and generate a knowledge graph from its content.
    """
    METADATA = CapabilityMetadata(
        id="org.ontobdc.domain.social.capability.query.extract_transform_public_weblink",
        version="0.1.0",
        name="Extract Transform Public Web Link",
        description="Fetches a public web link and transforms its content into an RDF Knowledge Graph.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["social", "weblink", "graph", "rdf"],
            "pt": ["social", "link", "web", "grafo", "rdf"],
        },
        supported_languages=["en", "pt"],
        input_schema={
            "type": "object",
            "properties": {
                "public_url": {
                    "type": "string",
                    "uri": "org.ontobdc.domain.social.weblink.public_url",
                    "required": True,
                    "description": "The URL of the web link to extract",
                }
            },
        },
        output_schema={
            "type": DocumentKnowledgeGraphPort,
            "properties": {
                "org.ontobdc.domain.social.document.data_resource": {
                    "type": "object",
                    "description": "Knowledge graph representation of the web link's content",
                },
            },
        },
        raises=[
            {
                "code": "org.ontobdc.domain.social.exception.weblink.fetch.failed",
                "python_type": "ValueError",
                "description": "Failed to fetch or parse the web link",
            }
        ],
    )

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": "Extract Transform Public Web Link",
            "pt": "Extrair e Transformar Link Web Público",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": "Fetches a public web link and transforms its content into an RDF Knowledge Graph.",
            "pt": "Busca um link web público e transforma seu conteúdo em um Grafo de Conhecimento RDF.",
        }
        return descriptions.get(lang, descriptions["en"])

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        url: str = context.get_parameter_value("public_url")
        graph = rdflib.Graph()
        
        try:
            # Add headers to avoid 403 Forbidden on some strict servers
            req = urllib.request.Request(
                url, 
                data=None, 
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; OntoBDC/0.9.0; +https://brasidatacenter.com)"
                }
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                content_type = response.headers.get("Content-Type", "")
                content = response.read()

                # Try guessing format from content type
                format_guess = None
                if "application/ld+json" in content_type:
                    format_guess = "json-ld"
                elif "text/turtle" in content_type or "application/x-turtle" in content_type:
                    format_guess = "turtle"
                elif "application/rdf+xml" in content_type:
                    format_guess = "xml"
                
                if format_guess:
                    try:
                        graph.parse(data=content, format=format_guess, publicID=url)
                    except Exception:
                        pass
                elif "text/html" in content_type or "application/xhtml+xml" in content_type:
                    # Step 1: Semantic parsing for embedded RDFa or JSON-LD
                    for fmt in ["rdfa", "json-ld"]:
                        try:
                            graph.parse(data=content.decode("utf-8", errors="ignore"), format=fmt, publicID=url)
                        except Exception:
                            pass
                            
                # Step 2: Content Scraping (HTML Metadata)
                if "text/html" in content_type or "application/xhtml+xml" in content_type:
                    self._scrape_html_content(url, content.decode("utf-8", errors="ignore"), graph)
                    
        except urllib.error.URLError as e:
            raise ValueError(f"Failed to reach the web link '{url}': {str(e)}")
        except Exception as e:
            raise ValueError(f"An error occurred while processing the web link '{url}': {str(e)}")

        return {
            "org.ontobdc.domain.social.weblink.graph": graph,
        }

    def _scrape_html_content(self, url: str, html_content: str, graph: rdflib.Graph) -> None:
        """
        Second step: Extracts basic HTML metadata (title, links, meta tags) and adds to the RDF graph.
        """
        class SimpleHTMLParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.title = None
                self.in_title = False
                self.links = set()
                self.meta_tags = []

            def handle_starttag(self, tag, attrs):
                if tag == "title":
                    self.in_title = True
                elif tag == "a":
                    for name, value in attrs:
                        if name == "href" and value.startswith("http"):
                            self.links.add(value)
                elif tag == "meta":
                    meta_attr = dict(attrs)
                    if "property" in meta_attr and "content" in meta_attr:
                        self.meta_tags.append((meta_attr["property"], meta_attr["content"]))
                    elif "name" in meta_attr and "content" in meta_attr:
                        self.meta_tags.append((meta_attr["name"], meta_attr["content"]))

            def handle_endtag(self, tag):
                if tag == "title":
                    self.in_title = False

            def handle_data(self, data):
                if self.in_title and not self.title:
                    self.title = data.strip()

        parser = SimpleHTMLParser()
        try:
            parser.feed(html_content)
        except Exception:
            pass

        # Build RDF Graph
        subject = rdflib.URIRef(url)
        graph.add((subject, RDF.type, FOAF.Document))
        
        # Add Title
        if parser.title:
            graph.add((subject, DC.title, rdflib.Literal(parser.title)))
            graph.add((subject, RDFS.label, rdflib.Literal(parser.title)))
            
        # Add Links
        for link in parser.links:
            graph.add((subject, FOAF.page, rdflib.URIRef(link)))
            
        # Add Meta tags (like og:title, og:description, twitter:image)
        for name, content in parser.meta_tags:
            if not name or not content:
                continue
            
            # Create a dynamic predicate for meta tags
            if name.startswith("og:"):
                ns = "http://ogp.me/ns#"
                prop = name.replace("og:", "", 1)
            elif name.startswith("twitter:"):
                ns = "http://twitter.com/ns#"
                prop = name.replace("twitter:", "", 1)
            else:
                ns = "http://schema.org/"
                prop = name
                
            predicate = rdflib.URIRef(f"{ns}{prop}")
            graph.add((subject, predicate, rdflib.Literal(content)))
