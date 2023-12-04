total_size=0
for file in $(find . -type f ! -path "./__pycache__*" ! -path "./.venv*" ! -path "./.git*"); do
    size=$(ls -l "$file" | awk '{print $5}')
    total_size=$((total_size + size))
done

echo "Total size of all files: $total_size bytes"

