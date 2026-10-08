interface Env {
  GITHUB_DISPATCH_TOKEN: string;
  GITHUB_OWNER: string;
  GITHUB_REPO: string;
  GITHUB_WORKFLOW: string;
  GITHUB_REF: string;
}

export default {
  async scheduled(
    _controller: ScheduledController,
    env: Env,
  ): Promise<void> {
    await dispatchWorkflow(env);
  },
};

async function dispatchWorkflow(env: Env): Promise<void> {
  if (!env.GITHUB_DISPATCH_TOKEN) {
    throw new Error("GITHUB_DISPATCH_TOKEN is not set");
  }

  const url = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/actions/workflows/${encodeURIComponent(env.GITHUB_WORKFLOW)}/dispatches`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${env.GITHUB_DISPATCH_TOKEN}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "tarkov-bot-cloudflare-cron",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ref: env.GITHUB_REF }),
  });

  if (response.status === 204) {
    return;
  }

  const body = (await response.text()).trim();
  throw new Error(
    `GitHub dispatch failed: HTTP ${response.status}${body ? ` ${body}` : ""}`,
  );
}
