from bs4 import BeautifulSoup


def extract_text_from_html(content: str) -> str:
    soup = BeautifulSoup(content, 'html.parser')
    text = '- '.join(soup.stripped_strings)
    return text