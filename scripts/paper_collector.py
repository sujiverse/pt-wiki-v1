#!/usr/bin/env python3
import os
import json
import time
import requests
from datetime import datetime
from collections import defaultdict
import difflib

PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
EMAIL = "bot@ptcompensation.wiki"
GRAPH_FILE = "../docs/graph.json"
SEARCH_QUERIES = [
    "calf pain compensation patterns",
    "lower limb biomechanical dysfunction",
    "muscle fatigue calf",
    "vascular insufficiency leg pain",
    "nerve compression lower extremity",
    "ankle instability rehabilitation",
    "hip weakness physical therapy",
    "plantar fasciitis treatment"
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

def translate_to_korean(title):
    """간단한 키워드 기반 한국어 번역"""
    translations = {
        'gait': '보행',
        'analysis': '분석',
        'lower limb': '하지',
        'lower-limb': '하지',
        'amputation': '절단',
        'prosthetic': '의족',
        'hip': '고관절',
        'biomechanics': '생체역학',
        'hop': '호핑',
        'stabilization': '안정화',
        'training': '훈련',
        'landing': '착지',
        'nocturnal': '야간',
        'leg cramps': '다리 경련',
        'neuromuscular': '신경근',
        'fatigue': '피로',
        'calf muscle': '종아리근',
        'activation': '활성화',
        'kinesio taping': '키네시오테이핑',
        'effects': '효과',
        'management': '치료',
        'lumbar': '요추',
        'spinal stenosis': '척추관 협착증',
        'phlebotonics': '정맥순환개선제',
        'venous insufficiency': '정맥부전',
        'chronic venous disease': '만성 정맥질환',
        'entrapment neuropathies': '신경포착증후군',
        'extremity': '사지',
        'peroneal nerve': '비골신경',
        'palsy': '마비',
        'evaluation': '평가',
        'muscle': '근육',
        'nerve': '신경',
        'compression': '압박',
        'vascular': '혈관',
        'blood flow': '혈류'
    }

    korean_title = title.lower()
    for eng, kor in translations.items():
        korean_title = korean_title.replace(eng, kor)

    # 첫 글자만 대문자로
    korean_title = korean_title.capitalize()
    return korean_title

def extract_clinical_info(paper):
    abstract = paper['abstract'].lower()
    title_korean = translate_to_korean(paper['title'])

    if 'muscle' in abstract or 'fatigue' in abstract:
        node_type = 'cause'
        label = f"{title_korean[:40]}..."
        color = '#ff9800'
    elif 'nerve' in abstract or 'compression' in abstract:
        node_type = 'cause'
        label = f"{title_korean[:40]}..."
        color = '#3f51b5'
    elif 'vascular' in abstract or 'blood flow' in abstract:
        node_type = 'cause'
        label = f"{title_korean[:40]}..."
        color = '#9c27b0'
    else:
        node_type = 'evidence'
        label = f"{title_korean[:40]}..."
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

def find_best_target_node(paper, graph):
    """논문 내용에 따라 최적의 연결 노드 찾기"""
    abstract = paper['abstract'].lower()
    title = paper['title'].lower()
    content = abstract + ' ' + title

    # 기존 노드들과의 연관성 점수 계산
    node_scores = []

    for node in graph['nodes']:
        if node['id'].startswith('paper-'):
            continue  # 논문 노드는 제외

        score = 0
        node_id = node['id']

        # 키워드 기반 점수 계산
        if 'muscle' in content or 'fatigue' in content:
            if 'muscle-fatigue' in node_id or 'gastrocnemius' in node_id or 'soleus' in node_id:
                score += 10
            elif 'atp' in node_id or 'lactate' in node_id or 'mitochondrial' in node_id:
                score += 8

        if 'nerve' in content or 'compression' in content or 'neuropath' in content:
            if 'nerve-compression' in node_id:
                score += 10
            elif 'tibialis' in node_id or 'fibularis' in node_id:
                score += 7

        if 'vascular' in content or 'blood' in content or 'venous' in content:
            if 'vascular-insufficiency' in node_id:
                score += 10

        if 'gait' in content or 'biomechanical' in content or 'movement' in content:
            if 'biomechanical-dysfunction' in node_id or 'gait-abnormality' in node_id:
                score += 10
            elif 'ankle' in node_id or 'hip' in node_id:
                score += 7

        if 'training' in content or 'exercise' in content:
            if 'training-load' in node_id or 'overuse' in node_id:
                score += 8

        if score > 0:
            node_scores.append((score, node_id))

    if node_scores:
        node_scores.sort(reverse=True)
        return node_scores[0][1]  # 가장 높은 점수의 노드

    return 'calf-pain'  # 기본값

def check_duplicate_title(graph, title):
    """제목 유사도 기반 중복 체크"""
    for node in graph['nodes']:
        if node['id'].startswith('paper-') and 'clinicalInfo' in node:
            existing_title = node['clinicalInfo']['references'][0]['title']
            similarity = difflib.SequenceMatcher(None, title.lower(), existing_title.lower()).ratio()
            if similarity > 0.8:  # 80% 이상 유사하면 중복으로 판단
                return True, node['id']
    return False, None

def add_paper_to_graph(graph, node, paper):
    existing_ids = {n['id'] for n in graph['nodes']}
    if node['id'] in existing_ids:
        return False, "Already exists (same PMID)"

    # 제목 유사도 기반 중복 체크
    is_duplicate, duplicate_id = check_duplicate_title(graph, paper['title'])
    if is_duplicate:
        return False, f"Duplicate title (similar to {duplicate_id})"

    # 최적 연결 노드 찾기
    target_node_id = find_best_target_node(paper, graph)

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
        'label': f"논문 증거 ({node['clinicalInfo']['references'][0]['year']})"
    }
    graph['edges'].append(edge)

    return True, f"Connected to {target_node_id}"

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
            success, message = add_paper_to_graph(graph, node, paper)
            if success:
                print(f"  [+] Added: {node['label']} (PMID: {pmid}) -> {message}")
                added_count += 1
            else:
                print(f"  [-] Skipped: {message} (PMID: {pmid})")

    if added_count > 0:
        save_graph(graph)
        print(f"\n[OK] Total added: {added_count} papers")
    else:
        print("\n[INFO] No new papers added")

if __name__ == '__main__':
    main()