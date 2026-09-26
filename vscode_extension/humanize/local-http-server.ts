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
import { TTSService } from './tts/tts-service.js';
import { StubTTSService } from './tts/stub-tts.js';

const _logger = new Logger('debug');

export class LocalHTTPServer {
  private server: http.Server | null = null;
  private readonly port: number;
  private readonly stateMachine: AvatarStateMachine;
  private readonly tts: TTSService;

  constructor(
    stateMachine: AvatarStateMachine,
    port: number = 5001,
    tts?: TTSService,
  ) {
    this.port = port;
    this.stateMachine = stateMachine;
    this.tts = tts ?? new StubTTSService();
  }

  /** Start the HTTP server */
  start(): void {
    this.server = http.createServer((req, res) => {
      const url = new URL(req.url ?? '/', `http://localhost:${this.port}`);
      const pathname = url.pathname;

      // CORS for external programs (curl, Python, browser scripts)
      const origin = req.headers.origin;
      if (origin && /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin)) {
        res.setHeader('Access-Control-Allow-Origin', origin);
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
        case '/api/avatar/message':
          this.handleMessage(req, res);
          break;
        case '/api/tts/speak':
          this.handleTTS(req, res);
          break;
        case '/api/tts/status':
          this.handleTTSStatus(res);
          break;
        case '/api/tts/stop':
          this.handleTTSStop(req, res);
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
    _logger.info('extension', `  POST http://localhost:${this.port}/api/avatar/message`);
    _logger.info('extension', `  POST http://localhost:${this.port}/api/tts/speak`);
    _logger.info('extension', `  GET  http://localhost:${this.port}/api/tts/status`);
    _logger.info('extension', `  POST http://localhost:${this.port}/api/tts/stop`);
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
      name: 'Humanize AI Avatar API',
      version: '1.0.0',
      endpoints: {
        state: 'GET /api/avatar/state',
        emotion: 'POST /api/avatar/emotion',
        message: 'POST /api/avatar/message',
        ttsSpeak: 'POST /api/tts/speak',
        ttsStatus: 'GET /api/tts/status',
        ttsStop: 'POST /api/tts/stop',
      },
      usage: {
        emotion: 'POST /api/avatar/emotion {"expression": "happy"}',
        message: 'POST /api/avatar/message {"expression":"happy","message":"Hello!","durationMs":5000}',
        ttsSpeak: 'POST /api/tts/speak {"text":"Hello world"}',
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

  /** POST /api/avatar/message — combined emotion + message in one call */
  private handleMessage(req: http.IncomingMessage, res: http.ServerResponse): void {
    let body = '';
    req.on('data', (chunk: Buffer) => { body += chunk.toString(); });
    req.on('end', () => {
      try {
        const data = JSON.parse(body);
        const expression = data.expression;
        const message = data.message;
        const durationMs = data.durationMs ?? 10000;

        if (!expression && !message) {
          _logger.warn('HTTP', 'POST /api/avatar/message: neither expression nor message provided');
          this.sendJSON(res, { error: 'At least one of "expression" or "message" must be provided' }, 400);
          return;
        }

        if (expression) {
          const success = this.stateMachine.setExpression(expression, durationMs);
          if (!success) {
            const expressions = this.stateMachine.getExpressionNames();
            _logger.warn('HTTP', `POST /api/avatar/message: unknown expression "${expression}"`);
            this.sendJSON(res, {
              error: `Unknown expression "${expression}"`,
              available: expressions,
            }, 400);
            return;
          }
          _logger.debug('HTTP', `POST /api/avatar/message: expression "${expression}" set (duration=${durationMs}ms)`);
        }

        if (message) {
          this.stateMachine.setMessage(message, durationMs);
          _logger.debug('HTTP', `POST /api/avatar/message: message set (expiry=${durationMs}ms)`);
        }

        const state = this.stateMachine.getCurrentState();
        this.sendJSON(res, {
          expression: state.expressionName,
          message: this.stateMachine.getMessage() ?? undefined,
          availableExpressions: this.stateMachine.getExpressionNames(),
        });
      } catch {
        _logger.warn('HTTP', 'POST /api/avatar/message: invalid JSON body');
        this.sendJSON(res, { error: 'Invalid JSON body' }, 400);
      }
    });
  }

  /** POST /api/tts/speak — send text to TTS engine */
  private handleTTS(req: http.IncomingMessage, res: http.ServerResponse): void {
    let body = '';
    req.on('data', (chunk: Buffer) => { body += chunk.toString(); });
    req.on('end', () => {
      try {
        const data = JSON.parse(body);
        const text = data.text;

        if (!text || typeof text !== 'string' || !text.trim()) {
          _logger.warn('HTTP', 'POST /api/tts/speak: missing or empty text');
          this.sendJSON(res, { error: 'Missing or empty "text" field' }, 400);
          return;
        }

        _logger.debug('HTTP', `POST /api/tts/speak: speaking "${text.slice(0, 60)}..."`);
        this.tts.speak(text);

        this.sendJSON(res, { status: 'speaking', text: text.slice(0, 100) });
      } catch {
        _logger.warn('HTTP', 'POST /api/tts/speak: invalid JSON body');
        this.sendJSON(res, { error: 'Invalid JSON body' }, 400);
      }
    });
  }

  /** GET /api/tts/status — return current TTS status */
  private handleTTSStatus(res: http.ServerResponse): void {
    const status = this.tts.getStatus();
    const available = this.tts.isAvailable();
    _logger.debug('HTTP', `GET /api/tts/status: status=${status}, available=${available}`);
    this.sendJSON(res, { status, available });
  }

  /** POST /api/tts/stop — stop TTS immediately */
  private handleTTSStop(_req: http.IncomingMessage, res: http.ServerResponse): void {
    _logger.debug('HTTP', 'POST /api/tts/stop: stopping TTS');
    this.tts.stop();
    this.sendJSON(res, { status: this.tts.getStatus() });
  }

  private sendJSON(res: http.ServerResponse, data: unknown, statusCode: number = 200): void {
    res.writeHead(statusCode, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(data));
  }
}
