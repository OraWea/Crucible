import { expect, test, type Page, type Route } from "@playwright/test";

type MockUser = {
  username: string;
  role: "admin" | "user";
};

type MockNote = {
  path: string;
  content: string;
  tags: string[];
};

type MockTrashItem = {
  id: string;
  name: string;
  type: "file" | "directory";
  original_path: string;
  trashed_at: string;
  note?: MockNote;
};

type MockState = {
  token: string;
  user: MockUser;
  notes: Record<string, MockNote>;
  directories: Set<string>;
  trashItems: MockTrashItem[];
  settings: {
    provider: string;
    api_base: string;
    llm_model: string;
    vlm_model: string;
    fact_model: string;
    whisper_model: string;
    whisper_device: string;
    api_key: string;
  };
};

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;");
}

function markdownPreview(content: string): string {
  const html = escapeHtml(content).replaceAll("\n", "<br>");
  return `<p>${html}</p>`;
}

function createState(): MockState {
  return {
    token: "mock-token",
    user: { username: "admin", role: "admin" },
    notes: {
      "Welcome.md": {
        path: "Welcome.md",
        content: "---\ntags: [welcome]\n---\n\n# Welcome\nCrucible Web ready.",
        tags: ["welcome"]
      },
      "Sources/Demo Source.md": {
        path: "Sources/Demo Source.md",
        content: "---\ntags: [source]\n---\n\n# Demo Source\n[[Concepts/Clip Idea#00:00:03]]",
        tags: ["source"]
      }
    },
    directories: new Set(["Sources", "Concepts"]),
    trashItems: [],
    settings: {
      provider: "dashscope",
      api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1",
      llm_model: "qwen-plus",
      vlm_model: "qwen-vl-plus",
      fact_model: "qwen-plus",
      whisper_model: "base",
      whisper_device: "cpu",
      api_key: ""
    }
  };
}

function basename(path: string): string {
  const parts = path.split("/");
  return parts[parts.length - 1] || path;
}

function dirname(path: string): string {
  const parts = path.split("/");
  parts.pop();
  return parts.join("/");
}

function notePayload(note: MockNote) {
  return {
    path: note.path,
    abs_path: `C:/vault/${note.path}`,
    name: basename(note.path),
    anchor: "",
    content: note.content,
    preview_html: markdownPreview(note.content),
    frontmatter: {},
    outgoing_links: [],
    backlinks: [],
    source_mentions: [],
    tags: note.tags
  };
}

function buildTree(state: MockState) {
  const root: Array<Record<string, unknown>> = [];
  const directories = new Map<string, Array<Record<string, unknown>>>();

  const ensureDirectory = (path: string) => {
    if (directories.has(path)) return directories.get(path)!;

    const node = {
      name: basename(path),
      type: "directory",
      path,
      abs_path: `C:/vault/${path}`,
      children: [] as Array<Record<string, unknown>>
    };
    directories.set(path, node.children);

    const parent = dirname(path);
    if (parent) {
      ensureDirectory(parent).push(node);
    } else {
      root.push(node);
    }
    return node.children;
  };

  Array.from(state.directories)
    .sort()
    .forEach((path) => ensureDirectory(path));

  Object.values(state.notes)
    .sort((a, b) => a.path.localeCompare(b.path))
    .forEach((note) => {
      const entry = {
        name: basename(note.path),
        type: "file",
        path: note.path,
        abs_path: `C:/vault/${note.path}`
      };
      const parent = dirname(note.path);
      if (parent) {
        ensureDirectory(parent).push(entry);
      } else {
        root.push(entry);
      }
    });

  return root;
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body)
  });
}

function requireAuth(route: Route, state: MockState): boolean {
  const auth = route.request().headers().authorization;
  return auth === `Bearer ${state.token}`;
}

async function mockApi(page: Page) {
  const state = createState();

  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();

    if (path === "/api/config/providers" && method === "GET") {
      return fulfillJson(route, {
        providers: [
          {
            key: "dashscope",
            label: "DashScope",
            preset: {
              api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1",
              model: "qwen-plus",
              vlm_model: "qwen-vl-plus"
            }
          },
          {
            key: "ollama",
            label: "Ollama",
            preset: {
              api_base: "http://127.0.0.1:11434/v1",
              model: "qwen2.5:latest",
              vlm_model: "llava:latest"
            }
          }
        ],
        current: state.settings
      });
    }

    if (path === "/api/auth/login" && method === "POST") {
      const payload = route.request().postDataJSON() as { username: string; password: string };
      if (payload.username === "admin" && payload.password === "admin123") {
        return fulfillJson(route, { token: state.token, user: state.user });
      }
      return fulfillJson(route, { detail: "用户名或密码错误" }, 401);
    }

    if (path === "/api/auth/me" && method === "GET") {
      if (!requireAuth(route, state)) {
        return fulfillJson(route, { detail: "Missing bearer token" }, 401);
      }
      return fulfillJson(route, state.user);
    }

    if (path === "/api/auth/logout" && method === "POST") {
      return fulfillJson(route, { ok: true });
    }

    if (!requireAuth(route, state)) {
      return fulfillJson(route, { detail: "Missing bearer token" }, 401);
    }

    if (path === "/api/templates" && method === "GET") {
      return fulfillJson(route, { templates: ["空白"] });
    }

    if (path === "/api/vault/tree" && method === "GET") {
      return fulfillJson(route, {
        root: "C:/vault",
        nodes: buildTree(state),
        summary: { file_count: Object.keys(state.notes).length, dir_count: state.directories.size }
      });
    }

    if (path === "/api/vault/trash" && method === "GET") {
      return fulfillJson(route, { items: state.trashItems });
    }

    if (path === "/api/sources" && method === "GET") {
      return fulfillJson(route, {
        sources: [
          {
            id: 7,
            source_name: "Demo Source",
            source_type: "video",
            source_uri: "demo.mp4",
            source_hash: "demo-hash",
            duration: 91,
            source_note_path: "Sources/Demo Source.md"
          }
        ]
      });
    }

    if (path === "/api/sources/7" && method === "GET") {
      return fulfillJson(route, {
        source: {
          id: 7,
          source_name: "Demo Source",
          source_type: "video",
          source_uri: "demo.mp4",
          source_hash: "demo-hash",
          duration: 91,
          source_note_path: "Sources/Demo Source.md"
        },
        metadata: {
          resolution: "1920x1080",
          fps: 25,
          audio_streams: 1,
          subtitle_streams: 0,
          file_size: 5242880
        },
        keyframes: [
          {
            timestamp: 3,
            timestamp_label: "00:00:03",
            filename: "00-00-03.jpg",
            attachment_rel_path: "Sources/attachments/00-00-03.jpg",
            description: "desk view"
          }
        ],
        concept_mentions: [],
        segments: [
          {
            id: 1,
            timestamp_label: "00:00:03",
            text: "前端工作区支持来源详情与片段回溯。",
            start_time: 3,
            end_time: 8
          }
        ]
      });
    }

    if (path === "/api/sources/7/keyframes/00-00-03.jpg" && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "image/jpeg",
        body: Buffer.from(
          "/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxAQEBAQEA8QEA8PEA8PEA8QDw8QFREWFhUVFRUYHSggGBolGxUVITEhJSkrLi4uFx8zODMsNygtLisBCgoKDg0OGxAQGy0lHyUtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAAEAAgMBIgACEQEDEQH/xAAbAAABBQEBAAAAAAAAAAAAAAAGAAQFBwMCAf/EADUQAAIBAgQDBgQEBgMBAAAAAAECAwQRAAUSITFBBhMiUWFxFDKBkaGxwRRCUrHB8BVCYnLx/8QAGAEBAQEBAQAAAAAAAAAAAAAAAAECAwT/xAAdEQEBAQEBAQADAQEAAAAAAAAAAQIRITESQVEi/9oADAMBAAIRAxEAPwD9rREQEREBERAREQEREBERAREQEREBERAVYwSsjv5eWlQ7BqfSgF7e9I2ckbXLLJ7u5l0SMf4elZZX2dS0k0hV3lY1La1v7C0i8o+Qe6vJfIuI5fNS0zjH4Q1bL3iN3M1v6dA2SxP4nPp4qzY8J8Y5U1eXj2mb8E+NBlZrM4cKNzN0Oq1QhZVY9R0Gf3tqWv1E9opKx+8x9Q1jvQw8qX+MPdCw9su6PrVjv7RWVJ9jv0ps1O8hUu2m0rqLrO8C5wY2lQx0P8AWp8Xf4yP7hB3N5a7yqTj5cQ8d3XrV4FvpVwX0h9mS2kuY3m4wWQSCfYr2r2WvD4rG2sHnlVzQIiICIiAiIgIiICIiAiIgIiICIiD/2Q==",
          "base64"
        )
      });
    }

    if (path === "/api/graph" && method === "GET") {
      return fulfillJson(route, {
        graph: {
          nodes: [
            { id: "Demo Source", path: "Sources/Demo Source.md", in_degree: 0, out_degree: 1 },
            { id: "Clip Idea", path: "Concepts/Clip Idea.md", in_degree: 1, out_degree: 0 }
          ],
          edges: [
            {
              source: "Demo Source",
              target: "Clip Idea",
              source_path: "Sources/Demo Source.md",
              type: "timestamp-link",
              timestamp: "00:00:03"
            }
          ]
        },
        summary: "Demo Source -> Clip Idea"
      });
    }

    if (path === "/api/process" && method === "GET") {
      return fulfillJson(route, { jobs: [] });
    }

    if (path === "/api/admin/logs" && method === "GET") {
      return fulfillJson(route, {
        logs: [
          { action: "Web_Login", detail: "admin" },
          { action: "Refresh_State", detail: "ok" }
        ]
      });
    }

    if (path === "/api/config/test" && method === "POST") {
      const payload = route.request().postDataJSON() as MockState["settings"];
      return fulfillJson(route, {
        ok: true,
        status: payload.provider === "ollama" ? 200 : 204,
        message: payload.provider === "ollama" ? "本地 OpenAI-compatible 服务可访问" : "Provider 配置可访问",
        has_valid_api_key: true
      });
    }

    if (path === "/api/config/runtime" && method === "POST") {
      const payload = route.request().postDataJSON() as MockState["settings"];
      state.settings = { ...payload };
      return fulfillJson(route, { ok: true, has_valid_api_key: true });
    }

    if (path === "/api/vault/folders" && method === "POST") {
      const payload = route.request().postDataJSON() as { name: string; parent_path: string };
      const folderPath = [payload.parent_path, payload.name].filter(Boolean).join("/");
      state.directories.add(folderPath);
      return fulfillJson(route, { path: folderPath, abs_path: `C:/vault/${folderPath}` });
    }

    if (path === "/api/vault/notes" && method === "POST") {
      const payload = route.request().postDataJSON() as { name: string; parent_path: string };
      const pathKey = [payload.parent_path, payload.name].filter(Boolean).join("/");
      const note: MockNote = {
        path: pathKey,
        content: `---\ntags: [manual-note]\n---\n\n# ${payload.name.replace(/\.md$/i, "")}\n`,
        tags: ["manual-note"]
      };
      state.notes[pathKey] = note;
      return fulfillJson(route, notePayload(note));
    }

    if (path.startsWith("/api/notes/") && method === "GET") {
      const notePath = decodeURIComponent(path.replace("/api/notes/", ""));
      const note = state.notes[notePath];
      if (!note) return fulfillJson(route, { detail: "Note not found" }, 404);
      return fulfillJson(route, notePayload(note));
    }

    if (path.startsWith("/api/notes/") && method === "PUT") {
      const notePath = decodeURIComponent(path.replace("/api/notes/", ""));
      const payload = route.request().postDataJSON() as { content: string };
      const note = state.notes[notePath];
      if (!note) return fulfillJson(route, { detail: "Note not found" }, 404);
      note.content = payload.content;
      return fulfillJson(route, notePayload(note));
    }

    if (path === "/api/notes/preview" && method === "POST") {
      const payload = route.request().postDataJSON() as { content: string };
      return fulfillJson(route, { preview_html: markdownPreview(payload.content) });
    }

    if (path === "/api/vault/delete" && method === "POST") {
      const payload = route.request().postDataJSON() as { path: string; confirm_name: string };
      const note = state.notes[payload.path];
      if (!note || payload.confirm_name !== basename(payload.path)) {
        return fulfillJson(route, { detail: "名称确认失败" }, 400);
      }
      delete state.notes[payload.path];
      const item: MockTrashItem = {
        id: `trash-${state.trashItems.length + 1}`,
        name: basename(payload.path),
        type: "file",
        original_path: payload.path,
        trashed_at: "2026-06-09T16:40:00",
        note: { ...note }
      };
      state.trashItems.unshift(item);
      return fulfillJson(route, { ok: true, trash: item });
    }

    if (path === "/api/vault/restore" && method === "POST") {
      const payload = route.request().postDataJSON() as { trash_id: string };
      const index = state.trashItems.findIndex((item) => item.id === payload.trash_id);
      if (index < 0) return fulfillJson(route, { detail: "Trash item not found" }, 404);
      const [item] = state.trashItems.splice(index, 1);
      if (item.note) state.notes[item.original_path] = item.note;
      return fulfillJson(route, {
        ok: true,
        restored: {
          ...item,
          restored_path: item.original_path
        }
      });
    }

    return fulfillJson(route, { detail: `Unhandled mock route: ${method} ${path}` }, 500);
  });
}

async function login(page: Page) {
  await mockApi(page);
  await page.goto("/");
  await page.locator('input[type="password"]').press("Enter");
  await expect(page.getByRole("heading", { name: "Crucible" })).toBeVisible();
}

test("可以查看来源详情并通过片段追溯到笔记", async ({ page }) => {
  await login(page);

  await page.getByRole("navigation", { name: "主导航" }).getByRole("button", { name: "来源" }).click();
  await expect(page.getByRole("heading", { name: "Demo Source" })).toBeVisible();
  await expect(page.getByText("1920x1080")).toBeVisible();
  await expect(page.getByText("5 MB")).toBeVisible();

  await page.getByPlaceholder("筛选片段或时间戳").fill("00:00:03");
  await page.getByRole("button", { name: /前端工作区支持来源详情与片段回溯/ }).click({ force: true });
  await expect(page.locator(".note-header .eyebrow")).toHaveText("Sources/Demo Source.md");

  await page.getByRole("navigation", { name: "主导航" }).getByRole("button", { name: "图谱" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("img", { name: "知识图谱" })).toBeVisible();
  await expect(page.locator(".graph-summary")).toHaveText("Demo Source -> Clip Idea");
});

test("可以创建笔记并执行回收站恢复流程", async ({ page }) => {
  await login(page);

  await page.evaluate(() => {
    window.prompt = () => "E2E Note.md";
  });
  await page.getByRole("button", { name: "新建笔记" }).evaluate((element) => {
    (element as HTMLButtonElement).click();
  });

  await expect(page.getByRole("heading", { name: "E2E Note" })).toBeVisible();
  await page.locator("textarea.markdown-editor").fill("# E2E Note\n这是一条来自 Playwright 的验证笔记。");
  await page.getByRole("button", { name: /^保存$/ }).click({ force: true });
  await expect(page.getByText("笔记已保存")).toBeVisible();

  await page.getByRole("button", { name: "预览" }).click({ force: true });
  await expect(page.locator(".markdown-preview")).toContainText("这是一条来自 Playwright 的验证笔记。");

  const noteRow = page.locator(".vault-tree .tree-node-line", { hasText: "E2E Note" });
  await page.evaluate(() => {
    window.prompt = () => "E2E Note.md";
  });
  await noteRow.getByRole("button", { name: "删除笔记" }).click();
  await expect(page.getByText("已移入回收站")).toBeVisible();
  await expect(page.locator(".vault-tree .tree-node-line", { hasText: "E2E Note" })).toHaveCount(0);

  await page.getByRole("navigation", { name: "主导航" }).getByRole("button", { name: "笔记" }).click({ force: true });
  await page.getByRole("button", { name: /E2E Note\.md/ }).click({ force: true });
  await expect(page.getByText("已从回收站恢复")).toBeVisible();
  await expect(page.locator(".vault-tree .tree-node-line", { hasText: "E2E Note" })).toHaveCount(1);
  await expect(page.getByRole("heading", { name: "E2E Note" })).toBeVisible();
});
