
import undetected_chromedriver as uc
import os
import time
import shutil

def open_browser_for_verification():
    print("🚀 Opening 1337x with Undetected Chromedriver...")
    
    # Ensure profile is fresh
    profile_dir = os.path.join(os.getcwd(), "selenium_profile")
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir)
            print("   🧹 Cleared old profile data.")
        except:
            pass
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)
        
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_dir}")
    
    try:
        # Undetected Chromedriver handles the driver creation and patching automatically
        driver = uc.Chrome(options=options, use_subprocess=True)
        
        # Go to 1337x
        driver.get("https://1337x.to/home")
        
        print("\n✅ Browser Open!")
        print("This browser is heavily modified to bypass Cloudflare.")
        print("1. If you see 'Verify', click it.")
        print("2. It should pass almost immediately.")
        print("3. Close the window when you see the homepage.")
        
        input("\n⌨️  Press Enter here AFTER you have solved the CAPTCHA and closed the browser... ")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    open_browser_for_verification()
