const http = require('http');
const port = 8080;

const server = http.createServer((req, res) => {
  res.statusCode = 200;
  res.setHeader('Content-Type', 'text/plain');
  res.end('Hello from our Golden Path App!\n');
});

server.listen(port, () => {
  console.log(`Server running on port ${port}`);
});