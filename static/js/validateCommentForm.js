function validateForm() {
  var comment = document.getElementById('comment').value;
  var name = document.getElementById('name').value;
  if (comment.length > 300) {
    alert('Please limit your comment to 300 characters.');
    return false;
  }
  if (name.length > 30) {
    alert('Please limit your name to 30 characters.');
    return false;
  }
  return true;
}