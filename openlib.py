import requests
import json

# Function to fetch book information from Open Library API
def fetch_book_info(book_query):
    base_url = "https://openlibrary.org/search.json"
    params = {'q': book_query, 'limit': 1}  # 'limit: 1' will give us only one result
    response = requests.get(base_url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if data['docs']:
            return data['docs'][0]  # Get the first result
        else:
            print(f"No results found for: {book_query}")
            return None
    else:
        print(f"Error fetching data for: {book_query}")
        return None

# Function to save the book data to a JSON file incrementally
def save_to_json(book_data, filename='books_info.json'):
    # Try to load existing data if the file already exists
    try:
        with open(filename, 'r') as json_file:
            books = json.load(json_file)
    except (FileNotFoundError, json.JSONDecodeError):
        books = []  # If file does not exist or is empty, start with an empty list

    # Append the new book data to the list
    books.append(book_data)

    # Write the updated list back to the file
    with open(filename, 'w') as json_file:
        json.dump(books, json_file, indent=4)

# Function to read the txt file and process each line
def process_books_from_file(filename):
    with open(filename, 'r') as file:
        for line in file:
            # Clean and split the line into book title and author
            parts = line.strip().split(' ', 1)  # Split at the first space to separate title and author
            if len(parts) == 2:
                book_query = f"{parts[0]} {parts[1]}"
                print(f"\nSearching for: {book_query}")
                book_info = fetch_book_info(book_query)
                print(book_info)
                
                if book_info:
                    book_data = {
                                "title": book_info.get('title', 'N/A'),
                                "subtitle": book_info.get('subtitle', 'N/A'),
                                "author": ', '.join(book_info.get('author_name', ['N/A'])),
                                "author_key": ', '.join(book_info.get('author_key', ['N/A'])),
                                "first_publish_year": book_info.get('first_publish_year', 'N/A'),
                                "edition_count": book_info.get('edition_count', 'N/A'),
                                "languages": ', '.join(book_info.get('language', ['N/A'])),
                                "has_fulltext": book_info.get('has_fulltext', False),
                                "ebook_access": book_info.get('ebook_access', 'N/A'),
                                "cover_url": f"https://covers.openlibrary.org/b/id/{book_info['cover_i']}-L.jpg" if 'cover_i' in book_info else 'No cover available',
                                "work_key": book_info.get('key', 'N/A'),
                                "cover_edition_key": book_info.get('cover_edition_key', 'N/A'),
                                "lending_identifier": book_info.get('lending_identifier_s', 'N/A'),
                                "ia": book_info.get('ia', []),  # Internet Archive identifiers
                            }

                    # Save the result immediately after getting it
                    save_to_json(book_data)
                print('-' * 50)
            else:
                print(f"Invalid line format: {line.strip()}")

# Main function
if __name__ == "__main__":
    filename = 'data.txt'  # Change this to the path of your text file
    process_books_from_file(filename)
