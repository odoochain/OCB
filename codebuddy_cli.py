"""CodeBuddy CLI — 通过 token 凭证调用 CodeBuddy"""

import asyncio
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from codebuddy_adapter import load_config, CodeBuddyClient, CodeBuddyAuth


async def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print('  python codebuddy_cli.py <prompt>           # 提问')
        print("  python codebuddy_cli.py auth              # 交互式登录获取新 token")
        print("  python codebuddy_cli.py status            # 查看当前 token 状态")
        sys.exit(1)

    cmd = sys.argv[1]
    config = load_config()

    if cmd == "auth":
        auth = CodeBuddyAuth(config)
        token = await auth.authenticate(open_browser=True)
        if token:
            print(f"\n登录成功! Token 已保存。")
        else:
            print("\n登录失败。")
        return

    if cmd == "status":
        from codebuddy_adapter import load_credentials, is_token_expired, DEFAULT_CREDS_DIR
        creds_dir = config.creds_dir or DEFAULT_CREDS_DIR
        credentials = load_credentials(creds_dir)
        if not credentials:
            print("No tokens found. Run 'python codebuddy_cli.py auth' to login.")
            return
        for i, cred in enumerate(credentials):
            expired = is_token_expired(cred)
            status = "EXPIRED" if expired else "valid"
            exp_info = f", expires in {cred.expires_in}s" if cred.expires_in else ""
            print(f"[{i}] {cred.file_path.name} — user: {cred.user_id}, status: {status}{exp_info}")
        return

    # 普通提问模式
    prompt = " ".join(sys.argv[1:])
    client = CodeBuddyClient(config)

    print(f"Mode: {client.mode}")
    print(f"Prompt: {prompt}\n")

    async for chunk in client.query_stream(
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Reply concisely."},
            {"role": "user", "content": prompt},
        ]
    ):
        print(chunk, end="", flush=True)
    print()


if __name__ == "__main__":
    asyncio.run(main())
