"""Resume parsing prompts — bilingual (en/zh)."""

RESUME_PARSE_EN = """You are a resume parser. Extract structured information from the following resume text.
Return ONLY a valid JSON object (no code fences, no additional text):

{{
  "name": "Full name of the candidate",
  "email": "Email address",
  "phone": "Phone number",
  "summary": "2-3 sentence summary of the candidate's profile",
  "skills": ["skill1", "skill2", ...],
  "experience_years": "junior|mid|senior (infer from total years of experience)",
  "experience": [
    {{"company": "Company name", "title": "Job title", "duration": "e.g. 2020-2023", "highlights": ["achievement", ...]}}
  ],
  "education": [
    {{"school": "Institution name", "degree": "BSc/MSc/PhD", "major": "Field of study", "year": "Graduation year"}}
  ],
  "projects": [
    {{"name": "Project name", "description": "Brief description", "tech_stack": ["tech1", "tech2"]}}
  ],
  "suggested_job_title": "Most appropriate job title based on recent experience"
}}

Resume text:
{resume_text}"""

RESUME_PARSE_ZH = """你是一个简历解析器。从以下简历文本中提取结构化信息。
只输出有效的 JSON 对象（不要代码块，不要额外文字）：

{{
  "name": "候选人姓名",
  "email": "邮箱地址",
  "phone": "电话号码",
  "summary": "2-3句话概括候选人背景",
  "skills": ["技能1", "技能2", ...],
  "experience_years": "junior|mid|senior（根据工作年限推断）",
  "experience": [
    {{"company": "公司名", "title": "职位", "duration": "如 2020-2023", "highlights": ["成就", ...]}}
  ],
  "education": [
    {{"school": "学校名", "degree": "学士/硕士/博士", "major": "专业", "year": "毕业年份"}}
  ],
  "projects": [
    {{"name": "项目名", "description": "简要描述", "tech_stack": ["技术1", "技术2"]}}
  ],
  "suggested_job_title": "根据最近经验推荐最合适的岗位名称"
}}

简历文本：
{resume_text}"""


def get_resume_parse_prompt(language: str = "en") -> str:
    """Return the resume parsing prompt template for the given language."""
    return RESUME_PARSE_ZH if language == "zh" else RESUME_PARSE_EN
