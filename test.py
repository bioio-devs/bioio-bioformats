extensions = []
with open('data.txt', 'r') as reader:
    for line in reader:
        extensions.append(line)
    
output = ",\n".join([f"\"{extension[:len(extension) - 1]}\"" for extension in sorted(list(set(extensions)))])
with open("output.txt", "w") as writer:
    writer.write(output)