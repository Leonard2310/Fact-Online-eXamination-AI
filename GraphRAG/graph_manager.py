import os
import sys
import time
import dotenv

import numpy as np
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import networkx as nx
from py2neo import Graph
from langchain_neo4j import Neo4jGraph

current_dir = os.getcwd()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from log import Logger
os.chdir(current_dir)

class GraphManager:
    def __init__(self, env_file="RAGkey.env"):
        dotenv.load_dotenv(env_file, override=True)
        self.logger = Logger(self.__class__.__name__).get_logger()
        
        # Neo4j connection parameters
        self.neo4j_url = os.environ["NEO4J_URI"].replace("http", "bolt")
        self.neo4j_username = os.environ["NEO4J_USERNAME"]
        self.neo4j_password = os.environ["NEO4J_PASSWORD"]

        # Initialize graph connection
        self.graph = Neo4jGraph(
            url=self.neo4j_url,
            username=self.neo4j_username,
            password=self.neo4j_password,
        )

        try:
            self.graph.query("RETURN 1")
            self.logger.info("Connessione a Neo4j stabilita con successo.")
        except Exception as e:
            self.logger.error(f"Errore durante la connessione a Neo4j: {e}")
            raise ConnectionError(f"Errore durante la connessione a Neo4j: {e}")

    def load_data(self, data):
        """
        Carica i dati nel grafo Neo4j.

        Args:
            data (list): Lista di dictionary contenenti le news.
        
        Raises:
            Exception: Se c'è un errore durante il caricamento dei dati.
        """

        q_load_articles = """
            UNWIND $data AS article
            MERGE (a:Article {title: article.TITLE})
            SET a.url = article.URL,
                a.body = article.BODY
            MERGE (s:Site {name: article.SITE})
            MERGE (a)-[:PUBLISHED_ON]->(s)

            WITH a, article
            // Gestisci le entità
            UNWIND article.ENTITY AS entity
            MERGE (e:Entity {name: entity})
            MERGE (a)-[:MENTIONS]->(e)

            WITH a, article, e
            // Gestisci i topic
            UNWIND article.TOPIC AS topic
            MERGE (t:Topic {name: topic})
            MERGE (a)-[:HAS_TOPIC]->(t)
        """
        
        self.logger.info(f"Avvio caricamento dati da {data}...")
        try:
            start_time = time.time()
            # Passa i dati come parametro, senza interpolazione diretta nella query
            self.graph.query(q_load_articles, params={"data": data})
            elapsed_time = time.time() - start_time
            self.logger.info(f"Caricamento completato in {elapsed_time:.2f} secondi.")
        except Exception as e:
            self.logger.error(f"Errore durante il caricamento dati: {e}")
        
        self.graph.refresh_schema()

    def extract_and_save_graph(self, output_file_topic, output_file_entity, output_file_site):
        """
        Esegue una query su Neo4j, crea il grafo e lo salva su file JPEG.
        """ 
        try:
            
            blue_light = "#add8e6"  # Blu chiaro

            graph = Graph(self.neo4j_url, auth=(self.neo4j_username, self.neo4j_password))
        
            def create_and_save_graph(query, node_relation, node_label, edge_label, output_file):
                """
                Crea e salva un grafo basato su una query Cypher e una relazione.
                """
                results = graph.run(query).to_data_frame()
                G = nx.DiGraph()
                
                # Aggiungi gli archi al grafo
                for _, row in results.iterrows():
                    G.add_edge(row[node_relation[0]], row[node_relation[1]], label=edge_label)

                # Generare una lista di colori per i nodi
                colors = list(mcolors.TABLEAU_COLORS.values())
                color_map = {}
                unique_nodes = results[node_relation[1]].unique()  # Associa nodi al secondo parametro della relazione
                for i, node in enumerate(unique_nodes):
                    color_map[node] = colors[i % len(colors)]  # Ricicla i colori se i nodi sono più dei colori disponibili

                # Colori per i nodi
                node_colors = []
                for node in G.nodes():
                    if node in color_map:
                        node_colors.append(color_map[node])
                    else:  # Se è un articolo, assegna un colore neutro
                        node_colors.append(blue_light)

                # Colori per le frecce (edge)
                edge_colors = []
                edge_labels = {}  # Per memorizzare le etichette degli archi
                for u, v, data in G.edges(data=True):
                    edge_colors.append(color_map[v])  # Colore della freccia basato sul nodo di destinazione
                    edge_labels[(u, v)] = data['label']  # Etichetta dell'arco

                # Abbreviazione etichette se troppo lunghe
                max_len = 15  # Lunghezza massima per ciascuna riga

                labels = {}

                def split_label(label, max_len):
                    # Suddividi l'etichetta in due righe senza troncare le parole
                    if len(label) <= max_len:
                        return label  # Nessuna divisione necessaria
                    
                    # Dividi la prima parte senza superare il limite di lunghezza
                    first_line = label[:max_len]
                    
                    # Trova l'ultimo spazio prima del limite per non troncare la parola
                    if len(first_line) == max_len:
                        first_line = first_line[:first_line.rfind(' ')]  # Trova l'ultimo spazio
                        second_line = label[len(first_line):]
                    else:
                        second_line = label[len(first_line):]
                    
                    # Se la seconda parte è troppo lunga, abbreviala (solo se necessario)
                    if len(second_line) > max_len:
                        second_line = second_line[:max_len] + "..."
                    
                    return f"{first_line}\n{second_line}"

                # Parametri di lunghezza
                max_len = 15  # Lunghezza massima per ciascuna riga

                labels = {}

                for node in G.nodes():
                    node_label = f"{node}"  # O qualsiasi altro testo da associare al nodo
                    
                    # Suddividi l'etichetta
                    label_text = split_label(node_label, max_len)
                    
                    labels[node] = label_text

                # Layout del grafico
                pos = nx.kamada_kawai_layout(G)

                # Aggiungi un po' di "spinta" per evitare sovrapposizioni
                def avoid_overlap(pos, G, threshold=0.1):
                    nodes = list(G.nodes())
                    overlap = True
                    while overlap:
                        overlap = False
                        for i, node_i in enumerate(nodes):
                            for j, node_j in enumerate(nodes):
                                if i >= j:
                                    continue
                                # Calcola la distanza tra due nodi
                                dist = np.linalg.norm(np.array(pos[node_i]) - np.array(pos[node_j]))
                                if dist < threshold:
                                    # Se troppo vicini, allontanali
                                    pos[node_i] = [pos[node_i][0] + 0.1, pos[node_i][1] + 0.1]
                                    pos[node_j] = [pos[node_j][0] - 0.1, pos[node_j][1] - 0.1]
                                    overlap = True
                                    break
                    return pos

                # Applica la funzione di evitamento delle sovrapposizioni
                pos = avoid_overlap(pos, G)

                # Disegna il grafico
                plt.figure(figsize=(12, 9))
                nx.draw(
                    G,
                    labels=labels,
                    pos=pos,
                    with_labels=True,
                    node_color=node_colors,
                    edge_color=edge_colors,
                    node_size=3500,
                    font_size=6,
                    width=2
                )

                # Disegna le etichette degli archi
                nx.draw_networkx_edge_labels(
                    G,
                    pos,
                    edge_labels=edge_labels,
                    font_size=6,
                    font_color="black"
                )

                plt.savefig(output_file, dpi=500)

            # Primo grafico: (Article)-[:HAS_TOPIC]->(Topic)
            query_topic = """
            MATCH (a:Article)-[:HAS_TOPIC]->(t:Topic)
            RETURN a.title AS Articolo,
                t.name AS Topic
            """
            create_and_save_graph(query_topic, node_relation=("Articolo", "Topic"), node_label="Topic", edge_label="HAS_TOPIC", output_file=output_file_topic)

            # Secondo grafico: (Article)-[:MENTIONS]->(Entity)
            query_mentions = """
            MATCH (a:Article)-[:MENTIONS]->(e:Entity)
            RETURN a.title AS Articolo,
                e.name AS Entity
            """
            create_and_save_graph(query_mentions, node_relation=("Articolo", "Entity"), node_label="Entity", edge_label="MENTIONS", output_file=output_file_entity)

            # Terzo grafico: (Article)-[:PUBLISHED_ON]->(Site)
            query_site = """
            MATCH (a:Article)-[:PUBLISHED_ON]->(s:Site)
            RETURN a.title AS Articolo,
                s.name AS Site
            """
            create_and_save_graph(query_site, node_relation=("Articolo", "Site"), node_label="Site", edge_label="PUBLISHED_ON", output_file=output_file_site)

            plt.show()
            self.logger.info("Grafi generati e salvati con successo.")
        except Exception as e:
            self.logger.error(f"Errore durante l'estrazione e il salvataggio del grafo: {e}")