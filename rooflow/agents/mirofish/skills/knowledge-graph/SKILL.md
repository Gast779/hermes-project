---
name: knowledge-graph
description: Build dynamic knowledge graphs from seed documents, news feeds, and market data using GraphRAG. Extract entities, relationships, and construct simulation-ready ontologies for MiroFish.
version: 1.0.0
author: MiroFish Agent
metadata:
  hermes:
    tags: [knowledge-graph, graphrag, ontology, entity-extraction, zep]
    category: prediction
    requires_toolsets: [terminal, execute_code, web_search]
---

# Knowledge Graph Construction

## When to Use

Use this skill when you need to:
- Build a knowledge graph from seed documents for MiroFish simulation
- Extract entities and relationships from news, reports, or market data
- Define ontology (entity types and relationship types) for a prediction scenario
- Prepare structured seed material for agent generation
- Update existing knowledge graphs with new information

## Quick Reference

| Step | Tool/Method | Output |
|------|------------|--------|
| 1. Gather seed material | Web search, file loading, API calls | Raw documents |
| 2. Generate ontology | LLM prompt or manual definition | Entity types + relations |
| 3. Build knowledge graph | Zep Cloud or Neo4j | Graph with nodes and edges |
| 4. Validate graph | Connectivity checks, orphan detection | Validated graph |
| 5. Export for simulation | JSON/GraphML format | Simulation-ready graph |

## Procedure

### 1. Gather and Structure Seed Material

```python
"""
Seed Material Template for MiroFish Simulations
Use this structure for maximum simulation quality.
"""

SEED_TEMPLATE = """
MARKET QUESTION:
[Clear, specific prediction question with date]

RESOLUTION RULES:
[Paste full rules verbatim]
Resolution source: [Official data provider]
End date: [Exact timestamp]
Known edge cases: [Any unusual conditions]

CURRENT MARKET STATE:
[YES/NO best bid/ask, midpoint, 24h volume, open interest]

BASE FACTS:
1. [Verifiable fact about current state]
2. [Verifiable fact about key entities]
3. [Verifiable fact about constraints]

RECENT HEADLINES:
1. [Relevant news from past 48 hours with source]
2. [Policy announcements or statements]
3. [Market-moving events]

KEY ENTITIES:
- People: [Names and roles]
- Institutions: [Organizations involved]
- Companies: [Corporate players]
- Regulators: [Government bodies]
- Media outlets: [Information sources]

BULL CASE (reasons YES occurs):
1. [Strongest argument for YES]
2. [Supporting evidence]
3. [Catalysts that would trigger YES]

BEAR CASE (reasons NO occurs):
1. [Strongest argument for NO]
2. [Obstacles and constraints]
3. [Catalysts that would trigger NO]

UNKNOWNS:
1. [Information gaps that matter]
2. [Upcoming events that could clarify]
3. [Unknowable factors]

PREDICTION TASK:
Estimate the probability of YES by market close.
Identify decisive catalysts that would move probability 10+ points.
Explain disagreement between different agent clusters.
Flag information that, if false, would break the forecast.
"""
```

### 2. Generate Ontology

```python
def generate_ontology(seed_material: str) -> dict:
    """
    Generate entity types and relationship types from seed material.
    
    Returns:
        {
            'entity_types': [
                {'name': 'Country', 'description': '...'},
                {'name': 'Organization', 'description': '...'},
                # ... 8-12 types
            ],
            'relation_types': [
                {'name': 'INFLUENCES', 'description': '...'},
                {'name': 'OPPOSES', 'description': '...'},
                # ... 5-8 types
            ]
        }
    """
    # Use LLM to extract ontology from seed material
    prompt = f"""
    Based on the following seed material, generate an ontology for a knowledge graph.
    
    Define 8-12 entity types (e.g., Country, Organization, Person, Event, Asset, etc.)
    Define 5-8 relationship types (e.g., INFLUENCES, OPPOSES, SUPPORTS, OWNS, etc.)
    
    Seed Material:
    {seed_material[:5000]}
    
    Return as structured JSON.
    """
    # Call LLM API
    return {}  # Parsed JSON response


# Standard ontology for crypto/polymarket scenarios
CRYPTO_ONTOLOGY = {
    'entity_types': [
        {'name': 'Cryptocurrency', 'description': 'Digital assets (BTC, ETH, etc.)'},
        {'name': 'Exchange', 'description': 'Trading platforms (Binance, Coinbase, etc.)'},
        {'name': 'Regulator', 'description': 'Government regulatory bodies'},
        {'name': 'Institution', 'description': 'Financial institutions and funds'},
        {'name': 'Person', 'description': 'Key individuals (founders, influencers)'},
        {'name': 'Event', 'description': 'Market-moving events'},
        {'name': 'Technology', 'description': 'Protocols, upgrades, innovations'},
        {'name': 'Market', 'description': 'Prediction markets (Polymarket, Kalshi)'},
        {'name': 'Media', 'description': 'News outlets and influencers'},
        {'name': 'Metric', 'description': 'On-chain and market metrics'},
    ],
    'relation_types': [
        {'name': 'INFLUENCES', 'description': 'Entity affects price or sentiment'},
        {'name': 'REGULATES', 'description': 'Regulatory authority over entity'},
        {'name': 'TRADES_ON', 'description': 'Asset listed on exchange'},
        {'name': 'SUPPORTS', 'description': 'Positive sentiment or backing'},
        {'name': 'OPPOSES', 'description': 'Negative sentiment or opposition'},
        {'name': 'CREATED', 'description': 'Entity created technology/protocol'},
        {'name': 'REPORTS_ON', 'description': 'Media coverage of entity'},
        {'name': 'CORRELATES_WITH', 'description': 'Price/metric correlation'},
    ]
}
```

### 3. Build Knowledge Graph with Zep Cloud

```python
import requests
import json
from typing import List, Dict

class ZepKnowledgeGraph:
    """Build and manage knowledge graphs using Zep Cloud."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.getzep.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"ApiKey {api_key}",
            "Content-Type": "application/json"
        }
    
    def create_graph(self, project_name: str, ontology: dict) -> str:
        """Create a new knowledge graph project."""
        url = f"{self.base_url}/api/v2/graph"
        payload = {
            "name": project_name,
            "ontology": ontology,
            "description": f"MiroFish knowledge graph for {project_name}"
        }
        
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()["uuid"]
    
    def add_documents(self, graph_uuid: str, documents: List[str]) -> dict:
        """Add seed documents to the graph for entity extraction."""
        url = f"{self.base_url}/api/v2/graph/{graph_uuid}/documents"
        
        payload = {
            "documents": [
                {"content": doc, "metadata": {"source": "seed"}}
                for doc in documents
            ]
        }
        
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()
    
    def get_graph_stats(self, graph_uuid: str) -> dict:
        """Get graph statistics: node count, edge count, connectivity."""
        url = f"{self.base_url}/api/v2/graph/{graph_uuid}/stats"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def validate_graph(self, graph_uuid: str) -> List[str]:
        """Validate graph: check for orphans, disconnected components."""
        stats = self.get_graph_stats(graph_uuid)
        issues = []
        
        # Check for orphaned nodes
        if stats.get("orphaned_nodes", 0) > 0:
            issues.append(f"Warning: {stats['orphaned_nodes']} orphaned nodes")
        
        # Check connectivity
        components = stats.get("connected_components", 0)
        if components > 3:
            issues.append(f"Warning: {components} disconnected components (ideally < 3)")
        
        # Check minimum size
        if stats.get("node_count", 0) < 20:
            issues.append(f"Warning: Only {stats['node_count']} nodes (minimum 20 recommended)")
        
        return issues
    
    def export_for_simulation(self, graph_uuid: str) -> dict:
        """Export graph in simulation-ready format."""
        url = f"{self.base_url}/api/v2/graph/{graph_uuid}/export"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()


# Local Neo4j alternative (offline mode)
class Neo4jKnowledgeGraph:
    """Build knowledge graphs using local Neo4j (offline mode)."""
    
    def __init__(self, uri: str = "bolt://localhost:7687", 
                 user: str = "neo4j", password: str = "password"):
        from neo4j import GraphDatabase
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def create_entities(self, entities: List[Dict]):
        """Create entity nodes in Neo4j."""
        with self.driver.session() as session:
            for entity in entities:
                session.run("""
                    MERGE (e:Entity {name: $name})
                    SET e.type = $type, e.description = $description
                """, name=entity['name'], type=entity['type'], 
                    description=entity.get('description', ''))
    
    def create_relationships(self, relationships: List[Dict]):
        """Create relationship edges in Neo4j."""
        with self.driver.session() as session:
            for rel in relationships:
                session.run("""
                    MATCH (a:Entity {name: $from}), (b:Entity {name: $to})
                    MERGE (a)-[r:RELATES {type: $type}]->(b)
                    SET r.description = $description
                """, from=rel['from'], to=rel['to'], 
                    type=rel['type'], description=rel.get('description', ''))
```

### 4. Complete Pipeline

```python
def build_knowledge_graph_pipeline(
    project_name: str,
    seed_material: str,
    ontology: dict = None,
    backend: str = "zep"
) -> dict:
    """
    Complete pipeline: seed -> ontology -> graph -> validation -> export.
    
    Args:
        project_name: Unique name for this prediction scenario
        seed_material: Structured seed documents
        ontology: Optional pre-defined ontology (auto-generated if None)
        backend: "zep" or "neo4j"
    
    Returns:
        dict with graph_uuid, stats, validation_issues, export_data
    """
    import os
    
    # Step 1: Generate ontology if not provided
    if ontology is None:
        ontology = generate_ontology(seed_material)
    
    # Step 2: Initialize backend
    if backend == "zep":
        kg = ZepKnowledgeGraph(api_key=os.getenv("ZEP_API_KEY"))
    else:
        kg = Neo4jKnowledgeGraph()
    
    # Step 3: Create graph
    graph_uuid = kg.create_graph(project_name, ontology)
    print(f"Created graph: {graph_uuid}")
    
    # Step 4: Add documents
    documents = [seed_material]  # Split into chunks if very long
    kg.add_documents(graph_uuid, documents)
    print("Documents added")
    
    # Step 5: Validate
    issues = kg.validate_graph(graph_uuid)
    for issue in issues:
        print(f"Validation: {issue}")
    
    # Step 6: Get stats
    stats = kg.get_graph_stats(graph_uuid)
    print(f"Graph stats: {stats['node_count']} nodes, {stats['edge_count']} edges")
    
    # Step 7: Export
    export_data = kg.export_for_simulation(graph_uuid)
    
    return {
        "graph_uuid": graph_uuid,
        "stats": stats,
        "validation_issues": issues,
        "export_data": export_data,
        "ontology": ontology
    }
```

## Pitfalls

- **Poor seed material**: Simulation quality depends directly on seed document quality
- **Overly complex ontology**: Too many entity types dilute simulation focus
- **Disconnected graph**: Orphaned nodes produce agents with no context
- **Stale data**: Always use fresh seed material — market conditions change fast
- **Ignoring validation**: Always check graph connectivity before simulation

## Verification

- Graph has minimum 20 nodes and 30 edges
- No orphaned nodes (or < 5%)
- Less than 3 disconnected components
- All key entities from seed material are represented
- Export format is compatible with MiroFish simulation engine
