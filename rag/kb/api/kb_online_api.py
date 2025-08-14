from pymilvus import MilvusClient, DataType
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import pdfplumber
from langchain.docstore.document import Document

# Replace with your Zilliz Cloud details
URI = "https://in03-56a0c941ed0ff6e.serverless.aws-eu-central-1.cloud.zilliz.com"
TOKEN = "f0cef636066c8653aa07cf9b435a2faf18dcb7a1e13a19a8c61c11b786f8a49d61c6a7d9d8837844c0b78ace482899432121c9cc"  # e.g., "root:your-secret-password"

# Initialize MilvusClient with a local database file
def create_milvus_client(uri, token):
    client = MilvusClient(
        uri=uri,
        token=token,
        secure=True
    )
    return client

def create_collection(collection_name):
  if not client.has_collection(collection_name):
    schema = client.create_schema(
      auto_id=True,          # Milvus generates IDs
      enable_dynamic_field=False  # We want fixed schema
    )

    # Add ALL fields to schema
    schema.add_field("id", DataType.INT64, is_primary=True)
    schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=384)
    schema.add_field("text", DataType.VARCHAR, max_length=65535)
    schema.add_field("book_title", DataType.VARCHAR, max_length=512)
    schema.add_field("chunk_order", DataType.INT32)
    schema.add_field("section_id", DataType.VARCHAR, max_length=256)

    client.create_collection(
      collection_name=collection_name,
      schema=schema,
      consistency_level="Strong"
    )
    if(not client.has_collection(collection_name)):
      print("Create collection failed")
      return None

    # Create index
    index_params = client.prepare_index_params(
      field_name="embedding",
      index_type="AUTOINDEX",
      metric_type="COSINE"
    )
    client.create_index(collection_name, index_params)
    client.load_collection(collection_name)

    print(f"✅ Collection '{collection_name}' created with metadata fields.")
    return 1

def search_with_context(query, context_window=2, limit=3000):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    client = create_milvus_client(URI, TOKEN)
    collections = client.list_collections()
    query_emb = model.encode([query], convert_to_tensor=False).tolist()

    retrieved_info = []
    for collection_name in collections:
        # 1. Find relevant chunk
        try:
            results = client.search(
                collection_name=collection_name,
                data=query_emb,
                limit=1,
                output_fields=["chunk_order", "section_id", "book_title"],
                search_params={"metric_type": "COSINE", "params": {"nprobe": 10}}
            )

            if not results or not results[0]:
                print(f"No results found in collection: {collection_name}")
                continue

            hit = results[0][0]
            order = hit["entity"]["chunk_order"]
            section = hit["entity"]["section_id"]

            # 2. Get neighbors using query()
            # Create proper list format for Milvus filter
            neighbor_orders = list(range(order - context_window, order + context_window + 1))
            neighbor_orders = [o for o in neighbor_orders if o >= 0]
            
            # Format the list properly for Milvus filter
            orders_str = str(neighbor_orders).replace('[', '').replace(']', '')
            
            neighbors = client.query(
                collection_name=collection_name,
                filter=f"section_id == '{section}' and chunk_order in [{orders_str}]",
                output_fields=["text", "chunk_order"],
                offset=0,
                limit=10
            )

            if not neighbors:  # Check if query returned any results
                print(f"No neighboring chunks found in {collection_name}")
                continue

            # Sort by order
            neighbors.sort(key=lambda x: x["chunk_order"])
            
            # Extract text from neighbors
            neighbor_texts = [n["text"] for n in neighbors]
            combined_text = "\n".join(neighbor_texts)
            
            # Create Document with the combined text
            doc = Document(f"\n----Source: {collection_name}----\n{combined_text}")
            retrieved_info.append(doc)
            
        except Exception as e:
            print(f"Error processing collection {collection_name}: {str(e)}")
            continue
            
    return retrieved_info

def extract_text_from_pdf(pdf_path, book_title):
    """Reliable PDF text extraction"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as e:
        if "Password required" in str(e):
            raise ValueError("PDF is encrypted! Try: pdfplumber.open(path, password='your_pass')") from e
        raise RuntimeError(f"PDF processing failed: {str(e)}") from e

def process_pdf(pdf_path, book_title):
    """COMPLETELY FITZ-FREE PDF PROCESSING"""
    book_collection = f"rag_{book_title}"
    collections = client.list_collections()
    check_stat = book_collection in collections

    print(f"{client.describe_collection(collection_name=book_collection)} and {book_collection}")
    if check_stat and client.get_collection_stats(collection_name=book_collection)['row_count'] != 0:
        print(f"Collection {book_collection} already exists and already injested")
        return

    # Create a seperate collection for new book
    if not check_stat:
      create_collection(book_collection)
    print("enter process")
    full_text = extract_text_from_pdf(pdf_path, book_title)

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=50)
    chunks = text_splitter.split_text(full_text)

    model = SentenceTransformer('all-MiniLM-L6-v2')
    embeddings = model.encode(chunks, convert_to_tensor=False)

    data = [{
        "embedding": emb.tolist(),
        "text": chunk,
        "book_title": book_title,
        "chunk_order": i,
        "section_id": f"{book_title}_ch{i//10}"
    } for i, (chunk, emb) in enumerate(zip(chunks, embeddings))]
    client.insert(book_collection, data)
    return book_collection