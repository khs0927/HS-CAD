export const MCP_APPS_PROTOCOL_VERSION = "2026-01-26";

export type DisplayMode = "inline" | "pip" | "fullscreen";
export type Theme = "light" | "dark";

export type SafeAreaInsets = {
  top: number;
  right: number;
  bottom: number;
  left: number;
};

export type HostContext = {
  theme?: Theme;
  displayMode?: DisplayMode;
  availableDisplayModes?: DisplayMode[];
  locale?: string;
  maxHeight?: number;
  maxWidth?: number;
  safeAreaInsets?: SafeAreaInsets;
  styles?: {
    variables?: Record<string, string>;
    css?: { fonts?: string };
  };
  [key: string]: unknown;
};

export type ToolResult = {
  structuredContent?: Record<string, unknown>;
  content?: unknown[];
  _meta?: Record<string, unknown>;
  isError?: boolean;
  [key: string]: unknown;
};

export type BridgeSnapshot = {
  status: "idle" | "connecting" | "connected" | "standalone" | "closed";
  hostContext: HostContext;
  hostCapabilities?: Record<string, unknown>;
  hostInfo?: { name?: string; version?: string; [key: string]: unknown };
  toolInput?: Record<string, unknown>;
  toolResult?: ToolResult;
  toolRevision: number;
  diagnostic?: string;
};

export type OpenAiCompatibility = {
  toolOutput?: unknown;
  toolInput?: unknown;
  toolResponseMetadata?: unknown;
  widgetState?: unknown;
  theme?: Theme;
  displayMode?: DisplayMode | string;
  locale?: string;
  maxHeight?: number;
  safeArea?: unknown;
  callTool?: (name: string, args: Record<string, unknown>) => Promise<unknown>;
  sendFollowUpMessage?: (message: { prompt: string; scrollToBottom?: boolean }) => Promise<void>;
  requestDisplayMode?: (request: { mode: DisplayMode }) => Promise<unknown>;
  setWidgetState?: (state: unknown) => void;
  notifyIntrinsicHeight?: (height?: number) => void;
};

export type OpenAiWindow = Window & { openai?: OpenAiCompatibility };

export const readOpenAi = (target: Window = window): OpenAiCompatibility | undefined =>
  (target as OpenAiWindow).openai;

type JsonRpcId = number | string;
type JsonRpcRequest = {
  jsonrpc: "2.0";
  id: JsonRpcId;
  method: string;
  params?: Record<string, unknown>;
};
type JsonRpcNotification = Omit<JsonRpcRequest, "id">;
type JsonRpcResponse = {
  jsonrpc: "2.0";
  id: JsonRpcId;
  result?: unknown;
  error?: { code?: number; message?: string; data?: unknown };
};

type PendingRequest = {
  resolve: (value: unknown) => void;
  reject: (reason: Error) => void;
  timeout: number;
};

type BridgeOptions = {
  eventWindow?: Window;
  targetWindow?: Window;
  initializeTimeoutMs?: number;
  requestTimeoutMs?: number;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const asFiniteNonNegative = (value: unknown): number | undefined =>
  typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : undefined;

const parseSafeArea = (value: unknown): SafeAreaInsets | undefined => {
  if (!isRecord(value)) return undefined;
  const source = isRecord(value.insets) ? value.insets : value;
  const top = asFiniteNonNegative(source.top);
  const right = asFiniteNonNegative(source.right);
  const bottom = asFiniteNonNegative(source.bottom);
  const left = asFiniteNonNegative(source.left);
  return top === undefined || right === undefined || bottom === undefined || left === undefined
    ? undefined
    : { top, right, bottom, left };
};

const compatibilityHostContext = (openai = readOpenAi()): HostContext => {
  if (!openai) return {};
  const displayMode = openai.displayMode;
  return {
    theme: openai.theme === "dark" ? "dark" : openai.theme === "light" ? "light" : undefined,
    displayMode: displayMode === "inline" || displayMode === "pip" || displayMode === "fullscreen"
      ? displayMode
      : undefined,
    locale: typeof openai.locale === "string" ? openai.locale : undefined,
    maxHeight: asFiniteNonNegative(openai.maxHeight),
    safeAreaInsets: parseSafeArea(openai.safeArea),
  };
};

const normalizeHostContext = (value: unknown): HostContext => {
  if (!isRecord(value)) return {};
  const dimensions = isRecord(value.containerDimensions) ? value.containerDimensions : {};
  const displayMode = value.displayMode;
  const theme = value.theme;
  return {
    ...value,
    theme: theme === "dark" ? "dark" : theme === "light" ? "light" : undefined,
    displayMode: displayMode === "inline" || displayMode === "pip" || displayMode === "fullscreen"
      ? displayMode
      : undefined,
    locale: typeof value.locale === "string" ? value.locale : undefined,
    maxHeight: asFiniteNonNegative(dimensions.maxHeight ?? value.maxHeight),
    maxWidth: asFiniteNonNegative(dimensions.maxWidth ?? value.maxWidth),
    safeAreaInsets: parseSafeArea(value.safeAreaInsets ?? value.safeArea),
    styles: isRecord(value.styles) ? value.styles as HostContext["styles"] : undefined,
  };
};

const normalizeToolResult = (value: unknown): ToolResult | undefined => {
  if (!isRecord(value)) return undefined;
  return {
    ...value,
    structuredContent: isRecord(value.structuredContent) ? value.structuredContent : undefined,
    content: Array.isArray(value.content) ? value.content : undefined,
    _meta: isRecord(value._meta) ? value._meta : undefined,
    isError: value.isError === true,
  };
};

const messageError = (error: JsonRpcResponse["error"], fallback: string): Error =>
  new Error(typeof error?.message === "string" ? error.message : fallback);

export class McpAppsBridge {
  private readonly eventWindow: Window;
  private readonly targetWindow: Window;
  private readonly initializeTimeoutMs: number;
  private readonly requestTimeoutMs: number;
  private readonly pending = new Map<string, PendingRequest>();
  private readonly listeners = new Set<(snapshot: BridgeSnapshot) => void>();
  private nextId = 1;
  private listening = false;
  private connectPromise?: Promise<boolean>;
  private snapshot: BridgeSnapshot = {
    status: "idle",
    hostContext: {},
    toolRevision: 0,
  };

  constructor(options: BridgeOptions = {}) {
    this.eventWindow = options.eventWindow ?? window;
    this.targetWindow = options.targetWindow ?? this.eventWindow.parent;
    this.initializeTimeoutMs = options.initializeTimeoutMs ?? 2_500;
    this.requestTimeoutMs = options.requestTimeoutMs ?? 20_000;
  }

  getSnapshot = (): BridgeSnapshot => ({
    ...this.snapshot,
    hostContext: {
      ...compatibilityHostContext(readOpenAi(this.eventWindow)),
      ...this.snapshot.hostContext,
    },
  });

  subscribe = (listener: (snapshot: BridgeSnapshot) => void): (() => void) => {
    this.listeners.add(listener);
    listener(this.getSnapshot());
    return () => this.listeners.delete(listener);
  };

  connect = (): Promise<boolean> => {
    if (this.connectPromise) return this.connectPromise;
    this.connectPromise = this.performConnect();
    return this.connectPromise;
  };

  private async performConnect(): Promise<boolean> {
    if (this.targetWindow === this.eventWindow) {
      this.update({ status: "standalone", hostContext: compatibilityHostContext(readOpenAi(this.eventWindow)) });
      return false;
    }

    this.startListening();
    this.update({ status: "connecting" });
    try {
      const value = await this.requestRaw("ui/initialize", {
        appInfo: { name: "HS-CAD Mobile", version: "0.3.0" },
        appCapabilities: { availableDisplayModes: ["inline", "fullscreen"] },
        protocolVersion: MCP_APPS_PROTOCOL_VERSION,
      }, this.initializeTimeoutMs);
      if (!isRecord(value) || !isRecord(value.hostInfo) || !isRecord(value.hostCapabilities)) {
        throw new Error("The host returned an invalid ui/initialize response.");
      }
      this.update({
        status: "connected",
        hostContext: normalizeHostContext(value.hostContext),
        hostCapabilities: value.hostCapabilities,
        hostInfo: value.hostInfo,
        diagnostic: undefined,
      });
      this.notify("ui/notifications/initialized", {});
      return true;
    } catch (error) {
      this.update({
        status: "standalone",
        hostContext: compatibilityHostContext(readOpenAi(this.eventWindow)),
        diagnostic: error instanceof Error ? error.message : "MCP Apps bridge unavailable.",
      });
      return false;
    }
  }

  close = (): void => {
    if (this.listening) this.eventWindow.removeEventListener("message", this.handleMessage);
    this.listening = false;
    for (const request of this.pending.values()) {
      this.eventWindow.clearTimeout(request.timeout);
      request.reject(new Error("MCP Apps bridge closed."));
    }
    this.pending.clear();
    this.update({ status: "closed" });
  };

  callTool = async (name: string, args: Record<string, unknown>): Promise<unknown | undefined> => {
    if (this.snapshot.status === "connected") {
      try {
        return await this.requestRaw("tools/call", { name, arguments: args });
      } catch (bridgeError) {
        if (!readOpenAi(this.eventWindow)?.callTool) throw bridgeError;
      }
    }
    const openai = readOpenAi(this.eventWindow);
    if (openai?.callTool) return openai.callTool(name, args);
    return undefined;
  };

  sendUserMessage = async (text: string): Promise<boolean> => {
    if (this.snapshot.status === "connected") {
      try {
        await this.requestRaw("ui/message", {
          role: "user",
          content: [{ type: "text", text }],
        });
        return true;
      } catch (bridgeError) {
        if (!readOpenAi(this.eventWindow)?.sendFollowUpMessage) throw bridgeError;
      }
    }
    const openai = readOpenAi(this.eventWindow);
    if (!openai?.sendFollowUpMessage) return false;
    await openai.sendFollowUpMessage({ prompt: text, scrollToBottom: true });
    return true;
  };

  updateModelContext = async (context: {
    content?: unknown[];
    structuredContent?: Record<string, unknown>;
  }): Promise<boolean> => {
    if (this.snapshot.status !== "connected") return false;
    await this.requestRaw("ui/update-model-context", context as Record<string, unknown>);
    return true;
  };

  requestFullscreen = async (): Promise<boolean> => {
    if (this.snapshot.status === "connected") {
      try {
        await this.requestRaw("ui/request-display-mode", { mode: "fullscreen" });
        return true;
      } catch (bridgeError) {
        if (!readOpenAi(this.eventWindow)?.requestDisplayMode) throw bridgeError;
      }
    }
    const openai = readOpenAi(this.eventWindow);
    if (!openai?.requestDisplayMode) return false;
    await openai.requestDisplayMode({ mode: "fullscreen" });
    return true;
  };

  persistWidgetState = (state: unknown): boolean => {
    const openai = readOpenAi(this.eventWindow);
    if (!openai?.setWidgetState) return false;
    openai.setWidgetState(state);
    return true;
  };

  reportSize = (width: number, height: number): void => {
    if (this.snapshot.status === "connected") {
      this.notify("ui/notifications/size-changed", { width, height });
    }
    readOpenAi(this.eventWindow)?.notifyIntrinsicHeight?.(height);
  };

  readCompatibilityPayload = (): {
    toolInput?: unknown;
    toolOutput?: unknown;
    toolResponseMetadata?: unknown;
    widgetState?: unknown;
  } => ({
    toolInput: readOpenAi(this.eventWindow)?.toolInput,
    toolOutput: readOpenAi(this.eventWindow)?.toolOutput,
    toolResponseMetadata: readOpenAi(this.eventWindow)?.toolResponseMetadata,
    widgetState: readOpenAi(this.eventWindow)?.widgetState,
  });

  refreshCompatibilityContext = (): void => {
    this.update({
      hostContext: {
        ...this.snapshot.hostContext,
        ...compatibilityHostContext(readOpenAi(this.eventWindow)),
      },
    });
  };

  private update(patch: Partial<BridgeSnapshot>): void {
    this.snapshot = { ...this.snapshot, ...patch };
    const snapshot = this.getSnapshot();
    for (const listener of this.listeners) listener(snapshot);
  }

  private startListening(): void {
    if (this.listening) return;
    this.listening = true;
    this.eventWindow.addEventListener("message", this.handleMessage);
  }

  private handleMessage = (event: MessageEvent): void => {
    if (event.source !== this.targetWindow || !isRecord(event.data) || event.data.jsonrpc !== "2.0") return;
    const data = event.data;
    if ((typeof data.id === "number" || typeof data.id === "string") && ("result" in data || "error" in data)) {
      const key = String(data.id);
      const request = this.pending.get(key);
      if (!request) return;
      this.eventWindow.clearTimeout(request.timeout);
      this.pending.delete(key);
      if (isRecord(data.error)) request.reject(messageError(data.error, "Host request failed."));
      else request.resolve(data.result);
      return;
    }

    if (typeof data.method !== "string") return;
    const params = isRecord(data.params) ? data.params : {};
    if (data.method === "ui/notifications/tool-input") {
      this.update({ toolInput: isRecord(params.arguments) ? params.arguments : {}, diagnostic: undefined });
    } else if (data.method === "ui/notifications/tool-result") {
      const toolResult = normalizeToolResult(params);
      if (toolResult) {
        this.update({ toolResult, toolRevision: this.snapshot.toolRevision + 1, diagnostic: undefined });
      }
    } else if (data.method === "ui/notifications/host-context-changed") {
      this.update({ hostContext: { ...this.snapshot.hostContext, ...normalizeHostContext(params) } });
    } else if (data.method === "ui/notifications/tool-cancelled") {
      this.update({ diagnostic: typeof params.reason === "string" ? params.reason : "Tool call cancelled." });
    } else if (data.method === "ping" || data.method === "ui/resource-teardown") {
      if (typeof data.id === "number" || typeof data.id === "string") this.respond(data.id, {});
      if (data.method === "ui/resource-teardown") this.update({ status: "closed" });
    }
  };

  private requestRaw(method: string, params: Record<string, unknown>, timeoutMs = this.requestTimeoutMs): Promise<unknown> {
    this.startListening();
    const id = `hscad-${this.nextId++}`;
    const message: JsonRpcRequest = { jsonrpc: "2.0", id, method, params };
    return new Promise((resolve, reject) => {
      const timeout = this.eventWindow.setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`${method} timed out.`));
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timeout });
      try {
        this.targetWindow.postMessage(message, "*");
      } catch (error) {
        this.eventWindow.clearTimeout(timeout);
        this.pending.delete(id);
        reject(error instanceof Error ? error : new Error(`Unable to send ${method}.`));
      }
    });
  }

  private notify(method: string, params: Record<string, unknown>): void {
    const message: JsonRpcNotification = { jsonrpc: "2.0", method, params };
    this.targetWindow.postMessage(message, "*");
  }

  private respond(id: JsonRpcId, result: unknown): void {
    const message: JsonRpcResponse = { jsonrpc: "2.0", id, result };
    this.targetWindow.postMessage(message, "*");
  }
}

export const mcpBridge = new McpAppsBridge();
