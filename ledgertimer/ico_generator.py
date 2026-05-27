from PIL import Image, ImageDraw

def create_time_tracker_icon():
    # Create a base image with a transparent background (256x256 for high-res icon)
    size = (256, 256)
    image = Image.new("RGBA", size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    
    # 1. Draw a rounded square background (matching your app's clean look)
    # Using a professional deep blue/slate color palette
    bg_color = "#1E88E5" 
    padding = 20
    draw.rounded_rectangle(
        [padding, padding, size[0] - padding, size[1] - padding],
        radius=45,
        fill=bg_color
    )
    
    # 2. Draw an outer white clock circle
    circle_padding = 55
    draw.ellipse(
        [circle_padding, circle_padding, size[0] - circle_padding, size[1] - circle_padding],
        outline="white",
        width=12
    )
    
    # 3. Draw clock hands (indicating a timer/tracking)
    center = (128, 128)
    # Hour hand (pointing up/right)
    draw.line([center, (165, 95)], fill="white", width=12, joint="round")
    # Minute hand (pointing straight up)
    draw.line([center, (128, 70)], fill="white", width=12, joint="round")
    
    # Center pin of the clock
    draw.ellipse([120, 120, 136, 136], fill="white")
    
    # 4. Save as a multi-resolution .ico file for Windows compatibility
    # Windows icons pack multiple sizes (16x16, 32x32, 48x48, 256x256) into one file
    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    image.save("app_icon.ico", format="ICO", sizes=icon_sizes)
    print("Icon 'app_icon.ico' generated successfully!")

if __name__ == "__main__":
    create_time_tracker_icon()