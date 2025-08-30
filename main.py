import json

import json
from typing import Dict, List, Any, Optional

def prune_brave_search_for_llm(search_data: Dict[str, Any], max_results: Optional[int] = 10) -> str:
    """
    Prunes Brave search results to extract key information for LLM analysis.
    
    Args:
        search_data: The raw Brave search JSON response
        max_results: Maximum number of web results to include (None for all)
    
    Returns:
        A formatted string containing the pruned search results
    """
    
    def extract_web_results(web_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract key information from web search results"""
        if not web_data or 'results' not in web_data:
            return []
        
        results = []
        web_results = web_data['results'][:max_results] if max_results else web_data['results']
        
        for result in web_results:
            pruned_result = {
                'title': result.get('title', ''),
                'url': result.get('url', ''),
                'description': result.get('description', ''),
                'source': result.get('profile', {}).get('name', ''),
                'age': result.get('age', ''),
                'content_type': result.get('subtype', 'generic')
            }
            results.append(pruned_result)
        
        return results
    
    def extract_video_results(video_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract key information from video search results"""
        if not video_data or 'results' not in video_data:
            return []
        
        results = []
        for video in video_data['results']:
            video_info = video.get('video', {})
            pruned_video = {
                'title': video.get('title', ''),
                'url': video.get('url', ''),
                'description': video.get('description', ''),
                'creator': video_info.get('creator', ''),
                'duration': video_info.get('duration', ''),
                'age': video.get('age', ''),
                'platform': video_info.get('publisher', '')
            }
            results.append(pruned_video)
        
        return results
    
    # Extract query information
    query_info = search_data.get('query', {})
    original_query = query_info.get('original', '')
    
    # Extract web results
    web_results = extract_web_results(search_data.get('web', {}))
    
    # Extract video results
    video_results = extract_video_results(search_data.get('videos', {}))
    
    # Format for LLM consumption
    formatted_output = f"""SEARCH QUERY: {original_query}

WEB RESULTS ({len(web_results)} results):
"""
    
    for i, result in enumerate(web_results, 1):
        formatted_output += f"""
{i}. {result['title']}
   Source: {result['source']} | Age: {result['age']}
   URL: {result['url']}
   Description: {result['description']}
   Content Type: {result['content_type']}
"""
    
    if video_results:
        formatted_output += f"\nVIDEO RESULTS ({len(video_results)} results):\n"
        for i, video in enumerate(video_results, 1):
            formatted_output += f"""
{i}. {video['title']}
   Creator: {video['creator']} | Platform: {video['platform']} | Duration: {video['duration']}
   Age: {video['age']}
   URL: {video['url']}
   Description: {video['description']}
"""
    
    return formatted_output

def prune_brave_search_json(search_data: Dict[str, Any], max_results: Optional[int] = 10) -> Dict[str, Any]:
    """
    Alternative function that returns structured JSON instead of formatted text.
    Useful if you prefer to format the output differently for your LLM.
    """
    
    query_info = search_data.get('query', {})
    
    pruned_data = {
        'query': query_info.get('original', ''),
        'web_results': [],
        'video_results': []
    }
    
    # Process web results
    web_data = search_data.get('web', {})
    if web_data and 'results' in web_data:
        web_results = web_data['results'][:max_results] if max_results else web_data['results']
        for result in web_results:
            pruned_data['web_results'].append({
                'title': result.get('title', ''),
                'url': result.get('url', ''),
                'description': result.get('description', ''),
                'source': result.get('profile', {}).get('name', ''),
                'age': result.get('age', ''),
                'content_type': result.get('subtype', 'generic')
            })
    
    # Process video results
    video_data = search_data.get('videos', {})
    if video_data and 'results' in video_data:
        for video in video_data['results']:
            video_info = video.get('video', {})
            pruned_data['video_results'].append({
                'title': video.get('title', ''),
                'url': video.get('url', ''),
                'description': video.get('description', ''),
                'creator': video_info.get('creator', ''),
                'duration': video_info.get('duration', ''),
                'age': video.get('age', ''),
                'platform': video_info.get('publisher', '')
            })
    
    return pruned_data



jsonnn = {
    "query": {
        "original": "Major tech companies software engineering hiring plans 2026 expansion",
        "show_strict_warning": False,
        "is_navigational": False,
        "is_news_breaking": False,
        "spellcheck_off": True,
        "country": "us",
        "bad_results": False,
        "should_fallback": False,
        "postal_code": "",
        "city": "",
        "header_country": "",
        "more_results_available": True,
        "state": "",
    },
    "mixed": {
        "type": "mixed",
        "main": [
            {"type": "web", "index": 0, "all": False},
            {"type": "web", "index": 1, "all": False},
            {"type": "videos", "all": True},
            {"type": "web", "index": 2, "all": False},
            {"type": "web", "index": 3, "all": False},
            {"type": "web", "index": 4, "all": False},
            {"type": "web", "index": 5, "all": False},
            {"type": "web", "index": 6, "all": False},
            {"type": "web", "index": 7, "all": False},
            {"type": "web", "index": 8, "all": False},
            {"type": "web", "index": 9, "all": False},
            {"type": "web", "index": 10, "all": False},
            {"type": "web", "index": 11, "all": False},
            {"type": "web", "index": 12, "all": False},
            {"type": "web", "index": 13, "all": False},
            {"type": "web", "index": 14, "all": False},
            {"type": "web", "index": 15, "all": False},
            {"type": "web", "index": 16, "all": False},
            {"type": "web", "index": 17, "all": False},
            {"type": "web", "index": 18, "all": False},
            {"type": "web", "index": 19, "all": False},
        ],
        "top": [],
        "side": [],
    },
    "type": "search",
    "videos": {
        "type": "videos",
        "results": [
            {
                "type": "video_result",
                "url": "https://www.youtube.com/watch?v=lNyKBmpGYzw&pp=0gcJCfwAo7VqN5tD",
                "title": "Google’s 2026 Engineer Hiring Roadmap—Revealed by CEO. - YouTube",
                "description": "Because of popular demand, I now offer 3 consultation options: either for your career as a developer, a business consult, or general tech/dev questions:🚀 Ca...",
                "age": "June 10, 2025",
                "page_age": "2025-06-10T17:31:57",
                "fetched_content_timestamp": 1755439933,
                "video": {
                    "duration": "08:42",
                    "creator": "Stefan Mischook",
                    "publisher": "YouTube",
                },
                "meta_url": {
                    "scheme": "https",
                    "netloc": "youtube.com",
                    "hostname": "www.youtube.com",
                    "favicon": "https://imgs.search.brave.com/Wg4wjE5SHAargkzePU3eSLmWgVz84BEZk1SjSglJK_U/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvOTkyZTZiMWU3/YzU3Nzc5YjExYzUy/N2VhZTIxOWNlYjM5/ZGVjN2MyZDY4Nzdh/ZDYzMTYxNmI5N2Rk/Y2Q3N2FkNy93d3cu/eW91dHViZS5jb20v",
                    "path": "› watch",
                },
                "thumbnail": {
                    "src": "https://imgs.search.brave.com/uJ2SYqg0Pj-bu-xHqDMHgQt3mtRpb6tJfho7NGS9IQo/rs:fit:200:200:1:0/g:ce/aHR0cHM6Ly9pLnl0/aW1nLmNvbS92aS9s/TnlLQm1wR1l6dy9t/YXhyZXNkZWZhdWx0/LmpwZw",
                    "original": "https://i.ytimg.com/vi/lNyKBmpGYzw/maxresdefault.jpg",
                },
            },
            {
                "type": "video_result",
                "url": "https://www.youtube.com/watch?v=yttZIY8jhmo",
                "title": "Ex-OpenAI Insider Reveals Software Engineers Are DONE By 2026! ...",
                "description": "In AI 2027, Daniel Kokotajlo and others, say software engineers as we know them could be obsolete. Around 8 months ago, Amazon's CEO made the same statement,...",
                "age": "June 5, 2025",
                "page_age": "2025-06-05T12:00:06",
                "fetched_content_timestamp": 1749217016,
                "video": {
                    "duration": "11:14",
                    "creator": "AI Dose",
                    "publisher": "YouTube",
                },
                "meta_url": {
                    "scheme": "https",
                    "netloc": "youtube.com",
                    "hostname": "www.youtube.com",
                    "favicon": "https://imgs.search.brave.com/Wg4wjE5SHAargkzePU3eSLmWgVz84BEZk1SjSglJK_U/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvOTkyZTZiMWU3/YzU3Nzc5YjExYzUy/N2VhZTIxOWNlYjM5/ZGVjN2MyZDY4Nzdh/ZDYzMTYxNmI5N2Rk/Y2Q3N2FkNy93d3cu/eW91dHViZS5jb20v",
                    "path": "› watch",
                },
                "thumbnail": {
                    "src": "https://imgs.search.brave.com/p2xkz3R67UpSIdIFKzwqq5e3ThkKO7o_BjNgERjWdWs/rs:fit:200:200:1:0/g:ce/aHR0cHM6Ly9pLnl0/aW1nLmNvbS92aS95/dHRaSVk4amhtby9t/YXhyZXNkZWZhdWx0/LmpwZw",
                    "original": "https://i.ytimg.com/vi/yttZIY8jhmo/maxresdefault.jpg",
                },
            },
            {
                "type": "video_result",
                "url": "https://www.youtube.com/watch?v=9PpNmDgUDH8",
                "title": "My Honest Thoughts on the Software Engineering Job Market in 2025 ...",
                "description": "Apply to see if you'd be a good fit for my mentorship program DevLaunch - https://training.devlaunch.us/tim?video=9PpNmDgUDH8Today I'm getting real about the...",
                "age": "May 25, 2025",
                "page_age": "2025-05-25T14:00:22",
                "fetched_content_timestamp": 1756115142,
                "video": {
                    "duration": "11:40",
                    "creator": "Tech With Tim",
                    "publisher": "YouTube",
                },
                "meta_url": {
                    "scheme": "https",
                    "netloc": "youtube.com",
                    "hostname": "www.youtube.com",
                    "favicon": "https://imgs.search.brave.com/Wg4wjE5SHAargkzePU3eSLmWgVz84BEZk1SjSglJK_U/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvOTkyZTZiMWU3/YzU3Nzc5YjExYzUy/N2VhZTIxOWNlYjM5/ZGVjN2MyZDY4Nzdh/ZDYzMTYxNmI5N2Rk/Y2Q3N2FkNy93d3cu/eW91dHViZS5jb20v",
                    "path": "› watch",
                },
                "thumbnail": {
                    "src": "https://imgs.search.brave.com/ePcl-3POQ92DQVj_qljnS0W2CqF_2j1vYwg0_gPU1s0/rs:fit:200:200:1:0/g:ce/aHR0cHM6Ly9pLnl0/aW1nLmNvbS92aS85/UHBObURnVURIOC9t/YXhyZXNkZWZhdWx0/LmpwZw",
                    "original": "https://i.ytimg.com/vi/9PpNmDgUDH8/maxresdefault.jpg",
                },
            },
            {
                "type": "video_result",
                "url": "https://www.youtube.com/shorts/iLssG94npL8",
                "title": "software engineers in 2025 vs 2026 #shorts - YouTube",
                "description": "AboutPressCopyrightContact usCreatorsAdvertiseDevelopersTermsPrivacyPolicy & SafetyHow YouTube worksTest new featuresNFL Sunday Ticket · © 2025 Google LLC",
                "age": "June 26, 2025",
                "page_age": "2025-06-26T19:00:50",
                "fetched_content_timestamp": 1751214296,
                "video": {
                    "duration": "00:31",
                    "creator": "Socially Inept",
                    "publisher": "YouTube",
                },
                "meta_url": {
                    "scheme": "https",
                    "netloc": "youtube.com",
                    "hostname": "www.youtube.com",
                    "favicon": "https://imgs.search.brave.com/Wg4wjE5SHAargkzePU3eSLmWgVz84BEZk1SjSglJK_U/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvOTkyZTZiMWU3/YzU3Nzc5YjExYzUy/N2VhZTIxOWNlYjM5/ZGVjN2MyZDY4Nzdh/ZDYzMTYxNmI5N2Rk/Y2Q3N2FkNy93d3cu/eW91dHViZS5jb20v",
                    "path": "› shorts  › iLssG94npL8",
                },
                "thumbnail": {
                    "src": "https://imgs.search.brave.com/H_RGNT5Z9ns66lx06aszweZwDVUt8C8TQMrjzOFhfWM/rs:fit:200:200:1:0/g:ce/aHR0cHM6Ly9pLnl0/aW1nLmNvbS92aS9p/THNzRzk0bnBMOC9v/YXIyLmpwZz9zcXA9/LW9heW13RWRDSlVE/RU5BRlNGV1FBZ0h5/cTRxcEF3d0lBUlVB/QUloQ2NBSEFBUVk9/JmFtcDtycz1BT240/Q0xDNURXMDR4anJ3/ajF6a3JHaDA2enU2/OS0yLV9R",
                    "original": "https://i.ytimg.com/vi/iLssG94npL8/oar2.jpg?sqp=-oaymwEdCJUDENAFSFWQAgHyq4qpAwwIARUAAIhCcAHAAQY=&amp;rs=AOn4CLC5DW04xjrwj1zkrGh06zu69-2-_Q",
                },
            },
            {
                "type": "video_result",
                "url": "https://www.instagram.com/reel/DJQjxasRgNp/",
                "title": "why are 2026 software engineering internships already open ...",
                "description": '10M Followers, 30 Following, 8 Posts - @reel on Instagram: ""',
                "video": {},
                "meta_url": {
                    "scheme": "https",
                    "netloc": "instagram.com",
                    "hostname": "www.instagram.com",
                    "favicon": "https://imgs.search.brave.com/kgdtgqUZQdNYzMKhbVXC5vthlFLPMJ0IOJAdFjEIRuk/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvN2RiYmJiZDA4/NTBkNWQ0ZmQ3NDE5/OGUxOGI4NzE5ZDI0/Zjk0M2ExMDkzZmJm/ODA0MmJiMzkwZjMy/ZDM4YWVkOS93d3cu/aW5zdGFncmFtLmNv/bS8",
                    "path": "› reel  › DJQjxasRgNp",
                },
            },
        ],
        "mutated_by_goggles": False,
    },
    "web": {
        "type": "search",
        "results": [
            {
                "title": "Predictions For The Tech Job Market In 2025",
                "url": "https://www.forbes.com/sites/jackkelly/2024/12/17/predictions-for-the-tech-job-market-in-2025/",
                "is_source_local": False,
                "is_source_both": False,
                "description": "The hiring landscape extends beyond domestic borders, with <strong>81% of U.S. engineering leaders planning to hire abroad</strong>. While this shift toward global talent acquisition reflects the industry&#x27;s adaptability and recognition of the diverse skill sets available internationally, the globalization and ...",
                "page_age": "2025-01-08T02:07:48",
                "profile": {
                    "name": "Forbes",
                    "url": "https://www.forbes.com/sites/jackkelly/2024/12/17/predictions-for-the-tech-job-market-in-2025/",
                    "long_name": "forbes.com",
                    "img": "https://imgs.search.brave.com/qg6-E4bARcUpS7pHuJ2FXSeQ2YI51iPfbI8wpUBx9tg/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvZWY0NWFiMTBk/YmY2MjkyN2M0MTI0/NmRkYTM3ZjQzMGJj/Y2Q2MTBkYjVmZjA2/OGRjODBhMTM1M2Yx/YmRlZTA1NS93d3cu/Zm9yYmVzLmNvbS8",
                },
                "language": "en",
                "family_friendly": True,
                "type": "search_result",
                "subtype": "generic",
                "is_live": False,
                "meta_url": {
                    "scheme": "https",
                    "netloc": "forbes.com",
                    "hostname": "www.forbes.com",
                    "favicon": "https://imgs.search.brave.com/qg6-E4bARcUpS7pHuJ2FXSeQ2YI51iPfbI8wpUBx9tg/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvZWY0NWFiMTBk/YmY2MjkyN2M0MTI0/NmRkYTM3ZjQzMGJj/Y2Q2MTBkYjVmZjA2/OGRjODBhMTM1M2Yx/YmRlZTA1NS93d3cu/Zm9yYmVzLmNvbS8",
                    "path": "› sites  › jackkelly  › 2024  › 12  › 17  › predictions-for-the-tech-job-market-in-2025",
                },
                "thumbnail": {
                    "src": "https://imgs.search.brave.com/bD0BM3NIJRgNO3sEdh98NBaPbQAVSRqHFSahJ5WjOtc/rs:fit:200:200:1:0/g:ce/aHR0cHM6Ly9pbWFn/ZWlvLmZvcmJlcy5j/b20vc3BlY2lhbHMt/aW1hZ2VzL2ltYWdl/c2VydmUvNjc2MTk2/YmQzNmQzMjYyZWNk/MDE1YmUyLzB4MC5q/cGc_Zm9ybWF0PWpw/ZyZhbXA7Y3JvcD0x/MTgwLDg4NSx4NzMs/eTAsc2FmZSZhbXA7/aGVpZ2h0PTkwMCZh/bXA7d2lkdGg9MTYw/MCZhbXA7Zml0PWJv/dW5kcw",
                    "original": "https://imageio.forbes.com/specials-images/imageserve/676196bd36d3262ecd015be2/0x0.jpg?format=jpg&amp;crop=1180,885,x73,y0,safe&amp;height=900&amp;width=1600&amp;fit=bounds",
                    "logo": False,
                },
                "age": "January 8, 2025",
            },
            {
                "title": "2025 Software Engineer Job Market: Hiring Trends & Skills in Demand",
                "url": "https://blog.getaura.ai/software-engineering-job-trends",
                "is_source_local": False,
                "is_source_both": False,
                "description": "<strong>Machinery (-51%) &amp; Logistics (-39%):</strong> Traditional manufacturing and supply chain sectors are cutting back on software hiring, likely due to automation reducing the need for additional workforce expansion or further macro issues.",
                "page_age": "2025-07-23T20:32:12",
                "profile": {
                    "name": "Getaura",
                    "url": "https://blog.getaura.ai/software-engineering-job-trends",
                    "long_name": "blog.getaura.ai",
                    "img": "https://imgs.search.brave.com/FgQP-O4KUrH8BUMi_fj73SuPznLVDaViR-WnligiHUk/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvODVhYjY5NGY5/OGY0YmZmZTVjMDcx/MWZmYWViNDlmNGZh/YWMxMTZlMWI4Mzhi/ZWE0YmFkZDg3MmE4/MzBlNDQzMy9ibG9n/LmdldGF1cmEuYWkv",
                },
                "language": "en",
                "family_friendly": True,
                "type": "search_result",
                "subtype": "generic",
                "is_live": False,
                "meta_url": {
                    "scheme": "https",
                    "netloc": "blog.getaura.ai",
                    "hostname": "blog.getaura.ai",
                    "favicon": "https://imgs.search.brave.com/FgQP-O4KUrH8BUMi_fj73SuPznLVDaViR-WnligiHUk/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvODVhYjY5NGY5/OGY0YmZmZTVjMDcx/MWZmYWViNDlmNGZh/YWMxMTZlMWI4Mzhi/ZWE0YmFkZDg3MmE4/MzBlNDQzMy9ibG9n/LmdldGF1cmEuYWkv",
                    "path": "  › home  › product  › resource hub  › august 2025 job market  › ai in the workplace  › aura events  › ai job trends for 2025  › alternative data  › best skills to have  › benchmarking  › workforce trends for 2025  › decision intelligence  › due diligence  › employee sentiment",
                },
                "thumbnail": {
                    "src": "https://imgs.search.brave.com/TjMrdwmwq0Tx4E2NVbtD4L6tgbonkFRx17VRYHAA2yg/rs:fit:200:200:1:0/g:ce/aHR0cHM6Ly9pbmZv/LmdldGF1cmEuYWkv/aHViZnMvc29mdHdh/cmUlMjBlbmdpbmVl/ci5qcGc",
                    "original": "https://info.getaura.ai/hubfs/software%20engineer.jpg",
                    "logo": False,
                },
                "age": "July 23, 2025",
            },
            {
                "title": "The State of the Software Engineering Job Market for 2025: Trends + What To Expect",
                "url": "https://lemon.io/blog/software-engineering-job-market/",
                "is_source_local": False,
                "is_source_both": False,
                "description": "<strong>Clear role definitions and thoughtful sourcing help cut through hiring noise</strong>. Focusing on alignment from the start leads to stronger hires and faster onboarding. As demand for technical talent grows, more startups are turning to offshore developers to scale efficiently.",
                "page_age": "2025-06-12T13:41:36",
                "profile": {
                    "name": "Lemon.io",
                    "url": "https://lemon.io/blog/software-engineering-job-market/",
                    "long_name": "lemon.io",
                    "img": "https://imgs.search.brave.com/zDYcVM78yfEf82uD2zopgqHW4mkNVkgtqfr29t-fNHs/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvNDg5MzkwZGQz/NDZmODEyNWExYTRm/NmVkMmNkZmVjMTFl/ZDc0NDZiZDQzZjlm/YWJlNzc2OWRiODE3/OGI3MjJmNC9sZW1v/bi5pby8",
                },
                "language": "en",
                "family_friendly": True,
                "type": "search_result",
                "subtype": "generic",
                "is_live": False,
                "meta_url": {
                    "scheme": "https",
                    "netloc": "lemon.io",
                    "hostname": "lemon.io",
                    "favicon": "https://imgs.search.brave.com/zDYcVM78yfEf82uD2zopgqHW4mkNVkgtqfr29t-fNHs/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvNDg5MzkwZGQz/NDZmODEyNWExYTRm/NmVkMmNkZmVjMTFl/ZDc0NDZiZDQzZjlm/YWJlNzc2OWRiODE3/OGI3MjJmNC9sZW1v/bi5pby8",
                    "path": "  › home  › blog  › industry insights & reports",
                },
                "thumbnail": {
                    "src": "https://imgs.search.brave.com/vJclqB6YhUjQCwonZfgaO6MtXYUeejsO2aH3tLcKdis/rs:fit:200:200:1:0/g:ce/aHR0cHM6Ly9sZW1v/bi5pby93cC1jb250/ZW50L3VwbG9hZHMv/MjAyNS8wNi9zb2Z0/d2FyZS1lbmdpbmVl/cmluZy1qb2ItbWFy/a2V0LWhlcm8ucG5n",
                    "original": "https://lemon.io/wp-content/uploads/2025/06/software-engineering-job-market-hero.png",
                    "logo": False,
                },
                "age": "June 12, 2025",
            },
            {
                "title": "Tech Job Market 2025: Recovery Outlook & Hiring Trends",
                "url": "https://unitedcode.net/when-will-the-tech-job-market-recover-2025-hiring-outlook-layoffs-and-policy-shifts/",
                "is_source_local": False,
                "is_source_both": False,
                "description": "Despite these reductions, tech job growth in specialty areas remains constant. Companies including <strong>Bank of America, Chase, and Wells Fargo</strong> have hired software engineers, AI engineers, and cybersecurity experts. This shift reflects a broader industry trend toward prioritizing jobs that drive ...",
                "profile": {
                    "name": "UnitedCode",
                    "url": "https://unitedcode.net/when-will-the-tech-job-market-recover-2025-hiring-outlook-layoffs-and-policy-shifts/",
                    "long_name": "unitedcode.net",
                    "img": "https://imgs.search.brave.com/5rWFDnuZch5-cbPAkt1OEX_qwADsAK3uL9SXtp7tF1I/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvZTNjM2Q4MTQ4/NTYzNjJjOTRlYjA2/YTBiMTlkMTE2NjZi/MjVhYzgzMTZmZjU0/ODBhNWUwZjAxOGM2/OTU2MTNkOC91bml0/ZWRjb2RlLm5ldC8",
                },
                "language": "en",
                "family_friendly": True,
                "type": "search_result",
                "subtype": "generic",
                "is_live": False,
                "meta_url": {
                    "scheme": "https",
                    "netloc": "unitedcode.net",
                    "hostname": "unitedcode.net",
                    "favicon": "https://imgs.search.brave.com/5rWFDnuZch5-cbPAkt1OEX_qwADsAK3uL9SXtp7tF1I/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvZTNjM2Q4MTQ4/NTYzNjJjOTRlYjA2/YTBiMTlkMTE2NjZi/MjVhYzgzMTZmZjU0/ODBhNWUwZjAxOGM2/OTU2MTNkOC91bml0/ZWRjb2RlLm5ldC8",
                    "path": "› when-will-the-tech-job-market-recover-2025-hiring-outlook-layoffs-and-policy-shifts",
                },
            },
            {
                "title": "$120k-$220k Software Engineer 2026 Jobs (NOW HIRING) Aug 2025",
                "url": "https://www.ziprecruiter.com/Jobs/Software-Engineer-2026",
                "is_source_local": False,
                "is_source_both": False,
                "description": "Position Software Engineering Co-op_Fall 2026 Location USA, Louisville, KY How You&#x27;ll Create Possibilities <strong>The Fall 2026 Software Engineering Co-op runs from August 17, 2026 - December 11, 2026</strong>, and ...",
                "profile": {
                    "name": "ZipRecruiter",
                    "url": "https://www.ziprecruiter.com/Jobs/Software-Engineer-2026",
                    "long_name": "ziprecruiter.com",
                    "img": "https://imgs.search.brave.com/2AFJwTW_SYg7GE9BGtHIfVHvzxFE6TV27j8AHlc-Wmo/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvNmUzNDgyZGM5/MGI3MTZlZWM1NzMx/NGMwZWMyMzFlOTEy/NWZhMDVlNzM2NzFm/NjY4YTM1YTkzNDAz/MDU2NmJjZi93d3cu/emlwcmVjcnVpdGVy/LmNvbS8",
                },
                "language": "en",
                "family_friendly": True,
                "type": "search_result",
                "subtype": "generic",
                "is_live": False,
                "meta_url": {
                    "scheme": "https",
                    "netloc": "ziprecruiter.com",
                    "hostname": "www.ziprecruiter.com",
                    "favicon": "https://imgs.search.brave.com/2AFJwTW_SYg7GE9BGtHIfVHvzxFE6TV27j8AHlc-Wmo/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvNmUzNDgyZGM5/MGI3MTZlZWM1NzMx/NGMwZWMyMzFlOTEy/NWZhMDVlNzM2NzFm/NjY4YTM1YTkzNDAz/MDU2NmJjZi93d3cu/emlwcmVjcnVpdGVy/LmNvbS8",
                    "path": "  › all jobs  › software engineer 2026 jobs",
                },
                "thumbnail": {
                    "src": "https://imgs.search.brave.com/ybfCFvvr2ydkziMPLaVkPc2PWXE7kzWXZ6SWyAbuMeI/rs:fit:200:200:1:0/g:ce/aHR0cHM6Ly93d3cu/emlwcmVjcnVpdGVy/LmNvbS9pbWcvZGVm/YXVsdC1vZy1pbWFn/ZS5qcGc",
                    "original": "https://www.ziprecruiter.com/img/default-og-image.jpg",
                    "logo": False,
                },
            },
            {
                "title": "Software Engineer 2026 Jobs, Employment | Indeed",
                "url": "https://www.indeed.com/q-software-engineer-2026-jobs.html",
                "is_source_local": False,
                "is_source_both": False,
                "description": "122 <strong>Software</strong> <strong>Engineer</strong> <strong>2026</strong> jobs available on Indeed.com. Apply to <strong>Software</strong> <strong>Engineer</strong>, <strong>Engineer</strong>, Senior <strong>Software</strong> <strong>Engineer</strong> and more!",
                "profile": {
                    "name": "Indeed",
                    "url": "https://www.indeed.com/q-software-engineer-2026-jobs.html",
                    "long_name": "indeed.com",
                    "img": "https://imgs.search.brave.com/dVfI8hv-wn8Trhad6qx-v2ReVTli6zMs81GApmPh8xM/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvZWY0ZDNjOGEw/ZTFkNzAxOTFlYWE2/NThjOWEyNzI4YjZj/NDQ4OWU1NDFiOTFm/NThmMjhjMmVjMzli/ZTY2YTQ4Ny93d3cu/aW5kZWVkLmNvbS8",
                },
                "language": "en",
                "family_friendly": True,
                "type": "search_result",
                "subtype": "generic",
                "is_live": False,
                "meta_url": {
                    "scheme": "https",
                    "netloc": "indeed.com",
                    "hostname": "www.indeed.com",
                    "favicon": "https://imgs.search.brave.com/dVfI8hv-wn8Trhad6qx-v2ReVTli6zMs81GApmPh8xM/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvZWY0ZDNjOGEw/ZTFkNzAxOTFlYWE2/NThjOWEyNzI4YjZj/NDQ4OWU1NDFiOTFm/NThmMjhjMmVjMzli/ZTY2YTQ4Ny93d3cu/aW5kZWVkLmNvbS8",
                    "path": "› q-software-engineer-2026-jobs.html",
                },
            },
            {
                "title": "2026 North America Software Engineering Internship | Careers",
                "url": "https://careers.thetradedesk.com/jobs/4787577007/2026-north-america-software-engineering-internship",
                "is_source_local": False,
                "is_source_both": False,
                "description": "Have a firm grasp on basic data structures and algorithmic techniques · Are a quick and self-directed learner. We provide close support and mentorship, but you will have ownership over the design, <strong>plan</strong>, and implementation of what you build. Are enrolled in a Bachelor&#x27;s or Master&#x27;s degree program · Are expected to graduate between Autumn <strong>2026</strong> ...",
                "profile": {
                    "name": "The Trade Desk",
                    "url": "https://careers.thetradedesk.com/jobs/4787577007/2026-north-america-software-engineering-internship",
                    "long_name": "careers.thetradedesk.com",
                    "img": "https://imgs.search.brave.com/0sh03XBmI-dwBvrngLuytpmnndxY2YHi34LaPv_aD6c/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvNTM4MGFlMWY4/YzgxMTYzOTk2NDFj/YTAzNDcwOTAwNTcz/NjExMmZhNDE4ZTYx/MmY0YjA2MWVkNmIz/MDZkNmJhYy9jYXJl/ZXJzLnRoZXRyYWRl/ZGVzay5jb20v",
                },
                "language": "en",
                "family_friendly": True,
                "type": "search_result",
                "subtype": "generic",
                "is_live": False,
                "meta_url": {
                    "scheme": "https",
                    "netloc": "careers.thetradedesk.com",
                    "hostname": "careers.thetradedesk.com",
                    "favicon": "https://imgs.search.brave.com/0sh03XBmI-dwBvrngLuytpmnndxY2YHi34LaPv_aD6c/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvNTM4MGFlMWY4/YzgxMTYzOTk2NDFj/YTAzNDcwOTAwNTcz/NjExMmZhNDE4ZTYx/MmY0YjA2MWVkNmIz/MDZkNmJhYy9jYXJl/ZXJzLnRoZXRyYWRl/ZGVzay5jb20v",
                    "path": "› jobs  › 4787577007  › 2026-north-america-software-engineering-internship",
                },
            },
            {
                "title": "What Companies Are Hiring Software Engineers? A Comprehensive Overview - Techneeds",
                "url": "https://www.techneeds.com/2025/01/23/what-companies-are-hiring-software-engineers-a-comprehensive-overview/",
                "is_source_local": False,
                "is_source_both": False,
                "description": "Major tech giants such as <strong>Google, Amazon, and Microsoft</strong> are not only expanding their teams but also adapting to the evolving needs of the market. This surge in hiring is echoed by mid-sized firms and startups in emerging industries like fintech and health tech, all vying for the same pool of talent.",
                "page_age": "2025-01-24T00:23:16",
                "profile": {
                    "name": "Techneeds",
                    "url": "https://www.techneeds.com/2025/01/23/what-companies-are-hiring-software-engineers-a-comprehensive-overview/",
                    "long_name": "techneeds.com",
                    "img": "https://imgs.search.brave.com/KTnyN_boL1Kl0ClNP5-jsWqrFDIDGfPCz98O4e-mFRs/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvZmFiYjQ0Mjk1/MWU1YTFkYTg3MjM4/NmY1OWM4Zjc2NWJm/ZDIwZjM1ZmNjNjAx/N2ZkMmE2ZGY5OGM4/ZTRhODJkNS93d3cu/dGVjaG5lZWRzLmNv/bS8",
                },
                "language": "en",
                "family_friendly": True,
                "type": "search_result",
                "subtype": "faq",
                "is_live": False,
                "meta_url": {
                    "scheme": "https",
                    "netloc": "techneeds.com",
                    "hostname": "www.techneeds.com",
                    "favicon": "https://imgs.search.brave.com/KTnyN_boL1Kl0ClNP5-jsWqrFDIDGfPCz98O4e-mFRs/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvZmFiYjQ0Mjk1/MWU1YTFkYTg3MjM4/NmY1OWM4Zjc2NWJm/ZDIwZjM1ZmNjNjAx/N2ZkMmE2ZGY5OGM4/ZTRhODJkNS93d3cu/dGVjaG5lZWRzLmNv/bS8",
                    "path": "  › home  › what companies are hiring software engineers? a comprehensive overview",
                },
                "thumbnail": {
                    "src": "https://imgs.search.brave.com/bK0a-UDLH4Fu7cfl98Zz28WpnYWZ2Pp-XYW09bxMrXI/rs:fit:200:200:1:0/g:ce/aHR0cHM6Ly93d3cu/dGVjaG5lZWRzLmNv/bS93cC1jb250ZW50/L3VwbG9hZHMvMjAy/NS8wNy93aGF0LWNv/bXBhbmllcy1hcmUt/aGlyaW5nLXNvZnR3/YXJlLWVuZ2luZWVy/cy1hLWNvbXByZWhl/bnNpdmUtb3ZlcnZp/ZXcuanBn",
                    "original": "https://www.techneeds.com/wp-content/uploads/2025/07/what-companies-are-hiring-software-engineers-a-comprehensive-overview.jpg",
                    "logo": False,
                },
                "age": "January 24, 2025",
            },
            {
                "title": "GitHub - vanshb03/New-Grad-2026: 2025 & 2026 New grad full-time roles in SWE, Quant, and PM.",
                "url": "https://github.com/vanshb03/New-Grad-2026",
                "is_source_local": False,
                "is_source_both": False,
                "description": "New Grad 2026: <strong>Machine Learning Engineer</strong> (Monetization Technology - TikTok Ads Creative &amp; Ecosystem)",
                "profile": {
                    "name": "GitHub",
                    "url": "https://github.com/vanshb03/New-Grad-2026",
                    "long_name": "github.com",
                    "img": "https://imgs.search.brave.com/xxsA4YxzaR0cl-DBsH9-lpv2gsif3KMYgM87p26bs_o/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvYWQyNWM1NjA5/ZjZmZjNlYzI2MDNk/N2VkNmJhYjE2MzZl/MDY5ZTMxMDUzZmY1/NmU3NWIzNWVmMjk0/NTBjMjJjZi9naXRo/dWIuY29tLw",
                },
                "language": "en",
                "family_friendly": True,
                "type": "search_result",
                "subtype": "software",
                "is_live": False,
                "meta_url": {
                    "scheme": "https",
                    "netloc": "github.com",
                    "hostname": "github.com",
                    "favicon": "https://imgs.search.brave.com/xxsA4YxzaR0cl-DBsH9-lpv2gsif3KMYgM87p26bs_o/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvYWQyNWM1NjA5/ZjZmZjNlYzI2MDNk/N2VkNmJhYjE2MzZl/MDY5ZTMxMDUzZmY1/NmU3NWIzNWVmMjk0/NTBjMjJjZi9naXRo/dWIuY29tLw",
                    "path": "› vanshb03  › New-Grad-2026",
                },
                "thumbnail": {
                    "src": "https://imgs.search.brave.com/nbjABYlaHOFnimJc9OuMNM66aG5qfq7WAxTGSu0rG1I/rs:fit:200:200:1:0/g:ce/aHR0cHM6Ly9vcGVu/Z3JhcGguZ2l0aHVi/YXNzZXRzLmNvbS8z/ODI0ODc3N2I4MTll/MTUyZTRhMjBmZGJj/YWE4MzNmNDhmMDZj/ODVlOWQ1OTZlZjE0/Yjk5MzBkNGJiZDgy/NmM1L3ZhbnNoYjAz/L05ldy1HcmFkLTIw/MjY",
                    "original": "https://opengraph.githubassets.com/38248777b819e152e4a20fdbcaa833f48f06c85e9d596ef14b9930d4bbd826c5/vanshb03/New-Grad-2026",
                    "logo": False,
                },
            },
            {
                "title": "Software Engineer, University Graduate, 2026",
                "url": "https://www.google.com/about/careers/applications/jobs/results/111007517923779270-software-engineer-university-graduate-2026",
                "is_source_local": False,
                "is_source_both": False,
                "description": "Bengaluru, Karnataka, India; Hyderabad, Telangana, India; +2 more; +1 more · Goleta, CA, USA; Los Angeles, CA, USA; +3 more; +2 more",
                "profile": {
                    "name": "Google",
                    "url": "https://www.google.com/about/careers/applications/jobs/results/111007517923779270-software-engineer-university-graduate-2026",
                    "long_name": "google.com",
                    "img": "https://imgs.search.brave.com/g17BH7ApM9d8-w9e-JPSNcH8j_6dKtlc-P0jl3lYp6Y/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvMGIyNDZlZGM5/Y2MxOTI5ODg1NTU5/YTA0YTYxNTEwMjZi/NTZlZDY4NGE2ODVm/OGVjNTg4MzE3ZDMz/YjdhNDI4Yi93d3cu/Z29vZ2xlLmNvbS8",
                },
                "language": "en",
                "family_friendly": True,
                "type": "search_result",
                "subtype": "generic",
                "is_live": False,
                "meta_url": {
                    "scheme": "https",
                    "netloc": "google.com",
                    "hostname": "www.google.com",
                    "favicon": "https://imgs.search.brave.com/g17BH7ApM9d8-w9e-JPSNcH8j_6dKtlc-P0jl3lYp6Y/rs:fit:32:32:1:0/g:ce/aHR0cDovL2Zhdmlj/b25zLnNlYXJjaC5i/cmF2ZS5jb20vaWNv/bnMvMGIyNDZlZGM5/Y2MxOTI5ODg1NTU5/YTA0YTYxNTEwMjZi/NTZlZDY4NGE2ODVm/OGVjNTg4MzE3ZDMz/YjdhNDI4Yi93d3cu/Z29vZ2xlLmNvbS8",
                    "path": "› about  › careers  › applications  › jobs  › results  › 111007517923779270-software-engineer-university-graduate-2026",
                },
            },
        ],
        "family_friendly": True,
    },
}


# Example usage with your data:
if __name__ == "__main__":
    # Using the text format (recommended for LLMs)
    llm_ready_text = prune_brave_search_for_llm(jsonnn, max_results=5)
    print(llm_ready_text)
    
    # Or using the JSON format
    llm_ready_json = prune_brave_search_json(jsonnn, max_results=5)
    print(json.dumps(llm_ready_json, indent=2))
