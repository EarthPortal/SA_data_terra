from rdflib import Graph, Namespace, URIRef, RDF, RDFS, OWL, SKOS
from argparse import ArgumentParser
from pathlib import Path

def load_rdf_vocabulary_from_uri(url):
    remote_graph = Graph()
    try:
        for fmt in ["xml", "turtle", "nt", "json-ld"]:
            try:
                remote_graph.parse(url, format=fmt)
                print(f"Loaded {len(remote_graph)} triples from {url} using format {fmt}")
                break  # Exit loop on successful parse
            except Exception:
                continue  # Try the next format
        else:
            raise ValueError(f"Failed to parse {url} in any recognized format.")
    except Exception as e:
        print(f"An error occurred while loading {url}: {e}")
    return remote_graph

def get_level_1_concepts_uris(graph):
    # Initialiser une liste pour stocker les URI des concepts de niveau 1
    level_1_concepts = []

    # Parcourir tous les triplets dans le graphe
    for subj, _, _ in graph:
        # Vérifier si le sujet du triplet est un concept (en utilisant SKOS concept)
        if (subj, RDF.type, SKOS.Concept) in graph:
            # Vérifier si le sujet n'est pas utilisé comme objet dans une relation skos:broader
            if (subj, SKOS.broader, None) not in graph:
                # Ajouter l'URI du concept de niveau 1 à la liste
                level_1_concepts.append(subj)

    return level_1_concepts

def get_concept_uris(graph):
    # Initialiser une liste pour stocker les URI des concepts
    concept_uris = []
    # Parcourir tous les triplets dans le graphe
    for subj, _, _ in graph:
        # Vérifier si le sujet du triplet est un concept (en utilisant SKOS concept)
        if (subj, RDF.type, SKOS.Concept) in graph:
            # Ajouter l'URI du concept à la liste
            concept_uris.append(subj)
    return concept_uris

# Enrichissement
def enrich_concepts_with_broader_relation(g, concept_uris, broader_concept_uri):
    # Parcourir tous les URI des concepts dans la liste
    for concept_uri in concept_uris:
        # Ajouter la relation skos:broader entre chaque concept et le concept plus large
        g.add((URIRef(concept_uri), SKOS.broader, URIRef(broader_concept_uri)))
    return g


def enrich_concepts_with_inScheme_relation(g, concept_uris, scheme_concept_uri):
    enriched_graph2 = Graph()
    # Parcourir tous les URI des concepts dans la liste
    for concept_uri in concept_uris:
        # Ajouter la relation skos:inScheme entre chaque concept et le concept plus large
        enriched_graph2.add((URIRef(concept_uri), SKOS.inScheme, URIRef(scheme_concept_uri)))
    return enriched_graph2


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-i", "--input", required=True, help="Input file to enrich")
    parser.add_argument("-o", "--output", help="Output file path and name")
    parser.add_argument("-c", "--concatenate", type=lambda s: s.split(','), help="Concatenate additional graphs at the URL(s) provided")
    args = parser.parse_args()
    path = ""
    if args.output != "":
        path = Path(args.output)
        
    final_graph = base_graph = Graph().parse(str(Path(args.input)), format="ttl")
    # Recuperation de l'URI du "super" scheme
    concept_uri_inScheme = next(base_graph.subjects(RDF.type, OWL.Ontology), None)

    concept_uri_schemes = {}
    # Chargement du contenu de chaque "sous" scheme
    for concept in base_graph.objects(subject=concept_uri_inScheme, predicate=SKOS.hasTopConcept):
        concept_uri_schemes[str(concept)] = load_rdf_vocabulary_from_uri(next(base_graph.objects(concept, RDFS.seeAlso), None))

    for concept_uri_broader, vocabulary_graph in concept_uri_schemes.items():
        # Enrichir les concepts existants avec la relation skos:broader et skos:inScheme
        enriched_graph= enrich_concepts_with_inScheme_relation(vocabulary_graph, get_concept_uris(vocabulary_graph),concept_uri_inScheme)
        final_graph = final_graph + enrich_concepts_with_broader_relation(enriched_graph, get_level_1_concepts_uris(vocabulary_graph), concept_uri_broader)
    
    if args.concatenate != None:
        for url in args.concatenate:
            final_graph += load_rdf_vocabulary_from_uri(url)

    final_graph.serialize(destination=str(args.output), format="ttl")
