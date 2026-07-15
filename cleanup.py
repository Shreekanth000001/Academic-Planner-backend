import asyncio
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from config import settings

# Initialize Supabase client
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

def cleanup_old_pdfs(days_old=7):
    print(f"[{datetime.now(timezone.utc)}] Starting Supabase cleanup job...")
    
    bucket_name = "syllabi"
    
    try:
        # 1. Ask Supabase for a list of all files in the bucket
        # Note: In production with millions of files, you would need to handle pagination here!
        files = supabase.storage.from_(bucket_name).list()
        
        files_to_delete = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        for file in files:
            # Supabase returns a 'name' and 'created_at' for each file
            file_name = file.get("name")
            created_at_str = file.get("created_at")
            
            if not file_name or not created_at_str or file_name == ".emptyFolderPlaceholder":
                continue
                
            # Parse the timestamp
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            
            # 2. Check if it's older than our cutoff
            if created_at < cutoff_date:
                files_to_delete.append(file_name)
                
        # 3. Batch delete the files
        if files_to_delete:
            print(f"Found {len(files_to_delete)} old files. Deleting...")
            supabase.storage.from_(bucket_name).remove(files_to_delete)
            print("Deletion successful.")
        else:
            print("No old files found. Storage is clean.")

    except Exception as e:
        print(f"Cleanup failed: {e}")

if __name__ == "__main__":
    cleanup_old_pdfs(days_old=7)