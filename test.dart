void main() { final u = Uri.parse('http://example.com/path').replace(queryParameters: {'token': 'my_api_key'}); print(u.toString()); }
