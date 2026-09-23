/**
 * LocalHTTPServer — exposes a REST API on localhost for external programs
 * to read and control the avatar state.
 *
 * Usage from any language:
 *   curl http://localhost:5001/api/avatar/state
 *   curl -X POST http://localhost:5001/api/avatar/emotion -H "Content-Type: application/json" -d '{"expression":"happy"}'
 */
import http from 'http';
import { Logger } from '../logger.js';
import { AvatarStateMachine } from './avatar/state-machine.js';

const _logger = new Logger('debug');

export class LocalHTTPServer {
  private server: http.Server | null = null;
  private readonly port: number;
  private readonly stateMachine: AvatarStateMachine;

  constructor(stateMachine: AvatarStateMachine, port: number = 5001) {
    this.port = port;
    this.stateMachine = stateMachine;
  }

  /** Start the HTTP server */
  start(): void {
    this.server = http.createServer((req, res) => {
      const url = new URL(req.url ?? '/', `http://localhost:${this.port}`);
      const pathname = url.pathname;

      // CORS for external programs (curl, Python, browser scripts) — no credentials involved
      const origin = req.headers.origin;
      if (origin && /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin)) {
        res.setHeader('Access-Control-Allow-Origin', origin);
      } else {
        res.setHeader('Access-Control-Allow-Origin', '*');
      }
      res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
      res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
      if (req.method === 'OPTIONS') {
        res.writeHead(200);
        res.end();
        return;
      }

      switch (pathname) {
        case '/api/avatar/state':
          this.handleState(res);
          break;
        case '/api/avatar/emotion':
          this.handleEmotion(req, res);
          break;
        case '/':
          this.handleRoot(res);
          break;
        default:
          this.sendJSON(res, { error: 'Not Found', path: pathname }, 404);
          break;
      }
    });

    this.server.listen(this.port, () => {
      _logger.info('extension', `Avatar API listening on http://localhost:${this.port}`);
    });

    // Log available endpoints
    _logger.info('extension', `  GET  http://localhost:${this.port}/api/avatar/state`);
    _logger.info('extension', `  POST http://localhost:${this.port}/api/avatar/emotion`);
  }

  /** Stop the HTTP server */
  stop(): void {
    if (this.server) {
      this.server.close(() => {
        _logger.debug('HTTPServer', 'Server stopped');
      });
      this.server = null;
    }
  }

  private handleRoot(res: http.ServerResponse): void {
    this.sendJSON(res, {
      name: 'Gamify AI Avatar API',
      version: '1.0.0',
      endpoints: {
        state: 'GET /api/avatar/state',
        emotion: 'POST /api/avatar/emotion',
      },
      usage: {
        emotion: 'POST /api/avatar/emotion {"expression": "happy"}',
      },
    });
  }

  private handleState(res: http.ServerResponse): void {
    const state = this.stateMachine.getCurrentState();
    const expressions = this.stateMachine.getExpressionNames();
    this.sendJSON(res, {
      current: state,
      available: expressions,
    });
  }

  private handleEmotion(req: http.IncomingMessage, res: http.ServerResponse): void {
    let body = '';
    req.on('data', (chunk: Buffer) => { body += chunk.toString(); });
    req.on('end', () => {
      try {
        const data = JSON.parse(body);
        const expression = data.expression;

        if (!expression) {
          this.sendJSON(res, { error: 'Missing "expression" field' }, 400);
          return;
        }

        const success = this.stateMachine.setExpression(expression);
        const current = this.stateMachine.getCurrentState();

        if (success) {
          this.sendJSON(res, { message: `Emotion set to "${expression}"`, state: current });
        } else {
          const expressions = this.stateMachine.getExpressionNames();
          this.sendJSON(res, {
            error: `Unknown expression "${expression}"`,
            available: expressions,
          }, 400);
        }
      } catch {
        this.sendJSON(res, { error: 'Invalid JSON body' }, 400);
      }
    });
  }

  private sendJSON(res: http.ServerResponse, data: unknown, statusCode: number = 200): void {
    res.writeHead(statusCode, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(data));
  }
}
