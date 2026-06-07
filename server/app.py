from flask import Flask, session
from flask_socketio import SocketIO
from flask_cors import CORS
import os
import uuid

# We will initialize the extensions here so blueprints can import them
socketio = SocketIO(cors_allowed_origins="*")

def create_app(cfg, mem):
    app = Flask(__name__)
    app.secret_key = os.urandom(24)
    
    # Configure CORS for the completely separate Next.js frontend
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    @app.before_request
    def ensure_session():
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())

    # Attach shared resources to app.config so blueprints can access them
    app.config['ALICE_CFG'] = cfg
    app.config['ALICE_MEM'] = mem
    
    socketio.init_app(app)

    # Register Blueprints
    from .routes.chat import chat_bp, init_chat_socketio
    from .routes.config import config_bp
    from .routes.market import market_bp
    from .routes.mcp import mcp_bp

    app.register_blueprint(chat_bp, url_prefix='/api')
    app.register_blueprint(config_bp, url_prefix='/api')
    app.register_blueprint(market_bp, url_prefix='/api')
    app.register_blueprint(mcp_bp, url_prefix='/api/mcp')

    # Initialize socket events
    init_chat_socketio(socketio, app)

    return app
