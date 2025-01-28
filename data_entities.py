from sqldb import Database
from csv_exporter import CSVExporter
import uuid
from log import Logger

class Claim:
    def __init__(self, text, claim_id=None, db=None):
        """
        Initializes a Claim object with text and optionally a provided claim ID. 
        It will also save the claim to the database.

        Args:
            text (str): The text of the claim.
            claim_id (str, optional): The ID of the claim. If not provided, a new UUID is generated.
            db (Database, optional): The database object to use. Defaults to a new Database instance.
        """
        self.logger = Logger(self.__class__.__name__).get_logger()
        self.db = db if db else Database()  
        self.id = claim_id if claim_id else str(uuid.uuid4())  
        self.text = text
        self.logger.info("Creating claim with ID: %s", self.id)
        self.save_to_db()

    def save_to_db(self):
        """
        Saves the claim to the database, creating the table if it doesn't exist.
        After saving, it exports the claims data to a CSV file.

        This method is also responsible for calling the `CSVExporter` to export claims data.
        """
        self.logger.info("Saving claim to the database.")
        create_table_sql = """
            CREATE TABLE IF NOT EXISTS claims (
                id TEXT PRIMARY KEY,
                text TEXT
            )
        """
        self.db.create_table(create_table_sql)
        self.db.execute_query("INSERT INTO claims (id, text) VALUES (?, ?)", (self.id, self.text))
        self.logger.info("Claim with ID %s saved to the database.", self.id)

        # Export the claims to CSV after insertion
        CSVExporter.export_claims(self.db)
        self.logger.info("Claims exported to CSV after insertion.")

    def get_sources(self):
        """
        Retrieves all sources associated with the claim from the database.

        Returns:
            list: A list of Source objects associated with this claim.
        """
        self.logger.info("Fetching sources for claim ID %s.", self.id)
        rows = self.db.fetch_all("SELECT * FROM sources WHERE claim_id = ?", (self.id,))
        sources = [Source(
            claim_id=row['claim_id'],
            title=row['title'],
            url=row['url'],
            site=row['site'],
            body=row['body'],
            entities=row['entities'],
            topic=row['topic'],
            source_id=row['id']
        ) for row in rows]
        self.logger.info("Found %d sources for claim ID %s.", len(sources), self.id)
        return sources

    def add_sources(self, sources_data):
        """
        Adds multiple sources associated with the claim to the database and exports the data to CSV.

        Args:
            sources_data (list of dict): A list of dictionaries containing source data to insert.
        """
        self.logger.info("Adding sources for claim ID %s.", self.id)
        create_table_sql = """
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                claim_id TEXT,
                title TEXT,
                url TEXT,
                site TEXT,
                body TEXT,
                entities TEXT,
                topic TEXT,
                FOREIGN KEY (claim_id) REFERENCES claims(id)
            )
        """
        self.db.create_table(create_table_sql)

        # Insert each source into the database
        for data in sources_data:
            self.db.execute_query("""
                INSERT INTO sources (id, claim_id, title, url, site, body, entities, topic)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (str(uuid.uuid4()), self.id, data['title'], data['url'], data['site'],
                  data['body'], data['entities'], data['topic']))

        # Export the sources to CSV after insertion
        CSVExporter.export_sources(self.db)
        self.logger.info("Sources for claim ID %s exported to CSV.", self.id)


class Source:
    def __init__(self, claim_id, title, url, site, body, entities, topic, source_id=None, db=None):
        """
        Initializes a Source object with details about a specific source.

        Args:
            claim_id (str): The ID of the associated claim.
            title (str): The title of the source.
            url (str): The URL of the source.
            site (str): The site of the source.
            body (str): The body/content of the source.
            entities (str): The entities mentioned in the source.
            topic (str): The topic of the source.
            source_id (str, optional): The ID of the source. If not provided, a new UUID is generated.
            db (Database, optional): The database object to use. Defaults to a new Database instance.
        """
        self.db = db if db else Database()
        self.id = source_id if source_id else str(uuid.uuid4())
        self.claim_id = claim_id
        self.title = title
        self.url = url
        self.site = site
        self.body = body
        self.entities = entities
        self.topic = topic

    @staticmethod
    def load_all(db=None):
        """
        Loads all source records from the database.

        Args:
            db (Database, optional): The database object to use. Defaults to a new Database instance.

        Returns:
            list: A list of Source objects loaded from the database.
        """
        db = db if db else Database()
        rows = db.fetch_all("SELECT * FROM sources")
        return [Source(
            claim_id=row['claim_id'],
            title=row['title'],
            url=row['url'],
            site=row['site'],
            body=row['body'],
            entities=row['entities'],
            topic=row['topic'],
            source_id=row['id'],
            db=db
        ) for row in rows]
