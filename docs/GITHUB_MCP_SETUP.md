# GitHub MCP Server Setup

## Overview

The GitHub MCP server enables Claude Code to interact with GitHub repositories, issues, pull requests, and more directly from the CLI.

## Configuration Status

✅ MCP server configuration created in `.claude.json`
⏳ **Pending: Add your GitHub Personal Access Token**

## Setup Steps

### 1. Create GitHub Personal Access Token

1. Go to [GitHub Settings → Developer Settings → Personal Access Tokens](https://github.com/settings/tokens)
2. Click **"Generate new token (classic)"**
3. Configure the token:
   - **Note**: `Claude Code MCP - Sports Betting`
   - **Expiration**: 90 days (or custom)
   - **Scopes** (select these):
     - ✅ `repo` - Full control of private repositories
     - ✅ `read:org` - Read org and team membership
     - ✅ `read:user` - Read user profile data
     - ✅ `user:email` - Access user email addresses

4. Click **"Generate token"**
5. **COPY THE TOKEN** (you won't see it again!)

### 2. Add Token to Configuration

**Option A: Environment Variable (Recommended - More Secure)**

1. Open your `.claude.json` file
2. Find the `"C:/Users/msenf/sports-betting"` project section
3. Locate the GitHub MCP server configuration (around line 730)
4. Replace `YOUR_GITHUB_TOKEN_HERE` with your actual token

**Example:**

```json
"github": {
  "type": "stdio",
  "command": "cmd",
  "args": [
    "/c",
    "npx",
    "-y",
    "@modelcontextprotocol/server-github"
  ],
  "env": {
    "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_YourActualTokenHere1234567890"
  }
}
```

**Option B: System Environment Variable (Most Secure)**

1. Set a system environment variable:

   ```powershell
   [System.Environment]::SetEnvironmentVariable('GITHUB_PERSONAL_ACCESS_TOKEN', 'ghp_your_token_here', 'User')
   ```

2. In `.claude.json`, the env section will automatically read from system variables

### 3. Test the Configuration

After adding your token:

1. **Restart Claude Code** completely (close all windows)
2. Navigate to your project:

   ```bash
   cd C:\Users\msenf\sports-betting
   ```

3. Check MCP server status:

   ```bash
   claude mcp list
   ```

4. You should see `github` with status ✅ connected

### 4. Verify GitHub MCP Tools

Once connected, you can use GitHub tools:

```bash
# List available GitHub MCP tools
claude mcp tools github

# Test basic functionality
claude "List my GitHub repositories"
```

## Available GitHub MCP Capabilities

Once configured, you'll have access to:

- 📁 **Repository Management**
  - List repositories
  - Create new repos
  - Get repo details
  - Search code

- 🐛 **Issues**
  - Create/update/close issues
  - List issues with filters
  - Add comments
  - Manage labels

- 🔀 **Pull Requests**
  - Create PRs
  - Review code changes
  - Merge PRs
  - Add review comments

- 📝 **Files & Content**
  - Read file contents
  - Create/update files
  - Push commits
  - Create branches

- 👥 **Collaboration**
  - Manage collaborators
  - Create releases
  - Manage webhooks

## Security Best Practices

1. ✅ **Use Fine-Grained Tokens** if you only need access to specific repos
2. ✅ **Set Expiration** - Tokens should expire (30-90 days recommended)
3. ✅ **Rotate Regularly** - Update tokens periodically
4. ✅ **Minimum Permissions** - Only grant scopes you actually need
5. ❌ **Never Commit** tokens to Git repositories
6. ❌ **Don't Share** tokens in chat, screenshots, or documentation

## Troubleshooting

### "Error: Incompatible auth server"

- **Cause**: Using HTTP endpoint instead of stdio
- **Fix**: Configuration already updated to use stdio

### "Error: 401 Unauthorized" or "Bad credentials"

- **Cause**: Invalid or missing token
- **Fix**: Double-check token is correctly copied into `.claude.json`

### "Server failed to start"

- **Cause**: Network issue or npm package not installing
- **Fix**:

  ```bash
  # Manually install the package first
  npx -y @modelcontextprotocol/server-github --help
  ```

### Token Expired

- **Symptoms**: Was working, now getting 401 errors
- **Fix**: Generate new token and update `.claude.json`

## Next Steps

After GitHub MCP is configured:

1. Initialize your sports-betting repository:

   ```bash
   git init
   git add .
   git commit -m "Initial commit: Sports betting model framework"
   ```

2. Create GitHub repository:

   ```bash
   claude "Create a new private GitHub repository called 'sports-betting'"
   ```

3. Push to GitHub:

   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/sports-betting.git
   git push -u origin master
   ```

## Questions?

If you encounter issues:

- Check Claude Code logs: `Get-Content ~\.claude\logs\main.log -Tail 50`
- Verify token permissions on GitHub
- Ensure token hasn't expired
