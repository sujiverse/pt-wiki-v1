#!/usr/bin/env python3
import os
import json
import time
import requests
from datetime import datetime
from collections import defaultdict

PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
EMAIL = "bot@ptcompensation.wiki"
GRAPH_FILE = "../docs/graph.json"
SEARCH_QUERIES = [
    "calf pain compensation patterns",
    "lower limb biomechanical dysfunction",
    "muscle fatigue calf",
    "vascular insufficiency leg pain",
    "nerve compression lower extremity"
]

def search_pubmed(query, max_results=5):
    params = {
        'db': 'pubmed',
        'term': query,
        'retmax': max_results,
        'retmode': 'json',
        'sort': 'relevance',
        'email': EMAIL
    }
    response = requests.get(f"{PUBMED_API}esearch.fcgi", params=params)
    data = response.json()
    return data.get('esearchresult', {}).get('idlist', [])

def fetch_paper_details(pmid):
    params = {
        'db': 'pubmed',
        'id': pmid,
        'retmode': 'xml',
        'email': EMAIL
    }
    response = requests.get(f"{PUBMED_API}efetch.fcgi", params=params)

    import xml.etree.ElementTree as ET
    root = ET.fromstring(response.content)

    article = root.find('.//Article')
    if not article:
        return None

    title = article.findtext('.//ArticleTitle', '')
    abstract = article.findtext('.//AbstractText', '')

    authors = []
    for author in article.findall('.//Author'):
        lastname = author.findtext('LastName', '')
        initials = author.findtext('Initials', '')
        if lastname:
            authors.append(f"{lastname} {initials}")

    year = article.findtext('.//PubDate/Year', '')

    return {
        'pmid': pmid,
        'title': title,
        'abstract': abstract,
        'authors': authors[:3],
        'year': year
    }

def extract_clinical_info(paper):
    abstract = paper['abstract'].lower()

    if 'muscle' in abstract or 'fatigue' in abstract:
        node_type = 'cause'
        label = f"{paper['title'][:30]}..."
        color = '#ff9800'
    elif 'nerve' in abstract or 'compression' in abstract:
        node_type = 'cause'
        label = f"{paper['title'][:30]}..."
        color = '#3f51b5'
    elif 'vascular' in abstract or 'blood flow' in abstract:
        node_type = 'cause'
        label = f"{paper['title'][:30]}..."
        color = '#9c27b0'
    else:
        node_type = 'evidence'
        label = f"{paper['title'][:30]}..."
        color = '#607d8b'

    evidence_strength = 0.7
    if 'systematic review' in abstract:
        evidence_strength = 0.95
    elif 'randomized' in abstract:
        evidence_strength = 0.85
    elif 'case study' in abstract:
        evidence_strength = 0.6

    return {
        'id': f"paper-{paper['pmid']}",
        'label': label,
        'type': node_type,
        'size': 15 + int(evidence_strength * 10),
        'importance': evidence_strength,
        'color': color,
        'clinicalInfo': {
            'description': paper['abstract'][:200] + '...',
            'evidence': f"{paper['title']} ({', '.join(paper['authors'])}, {paper['year']})",
            'references': [{
                'title': paper['title'],
                'authors': ', '.join(paper['authors']),
                'year': paper['year'],
                'pmid': paper['pmid']
            }]
        }
    }

def load_graph():
    graph_path = os.path.join(os.path.dirname(__file__), GRAPH_FILE)
    if os.path.exists(graph_path):
        with open(graph_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'nodes': [], 'edges': []}

def save_graph(graph):
    graph_path = os.path.join(os.path.dirname(__file__), GRAPH_FILE)
    with open(graph_path, 'w', encoding='utf-8') as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)

def add_paper_to_graph(graph, node, target_node_id='calf-pain'):
    existing_ids = {n['id'] for n in graph['nodes']}
    if node['id'] in existing_ids:
        return False

    import random
    node['x'] = (random.random() - 0.5) * 400
    node['y'] = (random.random() - 0.5) * 400

    graph['nodes'].append(node)

    edge = {
        'id': f"edge-{len(graph['edges']) + 1}",
        'source': node['id'],
        'target': target_node_id,
        'type': 'evidence',
        'weight': node['importance'],
        'label': f"Evidence: {node['clinicalInfo']['references'][0]['year']}"
    }
    graph['edges'].append(edge)

    return True

def main():
    print(f"[{datetime.now()}] Starting paper collection...")

    graph = load_graph()
    added_count = 0

    for query in SEARCH_QUERIES:
        print(f"Searching: {query}")
        pmids = search_pubmed(query, max_results=3)

        for pmid in pmids:
            time.sleep(0.5)
            paper = fetch_paper_details(pmid)
            if not paper:
                continue

            node = extract_clinical_info(paper)
            if add_paper_to_graph(graph, node):
                print(f"  ✅ Added: {node['label']} (PMID: {pmid})")
                added_count += 1
            else:
                print(f"  ⏭️  Skipped: already exists (PMID: {pmid})")

    if added_count > 0:
        save_graph(graph)
        print(f"\n✅ Total added: {added_count} papers")
    else:
        print("\nℹ️  No new papers added")

if __name__ == '__main__':
    main()