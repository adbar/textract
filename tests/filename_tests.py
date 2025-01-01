import os
import unittest

from trafilatura.filename import FilenameTemplate, generate_hash_filename


class TestFilenameTemplate(unittest.TestCase):
    """Test suite for FilenameTemplate class."""

    def test_template_validation_valid_templates(self):
        """Test that valid templates are accepted."""
        valid_templates = [
            "{hash}.{ext}",
            "{domain}/{path}.{ext}",
            "{domain}/{path_dirs}/{hash}.{ext}",
            "{domain}/{path_dirs}/{params}-{date}.{ext}",
            "{domain}/{path_dirs}/{lang}/{hash}.{ext}",
            "{file_basepath}/{file_basename}.{ext}",
            "{url}/{filename}.{ext}",
        ]
        for template in valid_templates:
            try:
                FilenameTemplate(template)
            except ValueError as e:
                self.fail(f"Valid template {template} raised ValueError: {str(e)}")

    def test_template_validation_invalid_templates(self):
        """Test that invalid templates raise appropriate errors."""
        invalid_templates = [
            "{unknown}.{ext}",  # Unknown variable
            "{domain\\path}.{ext}",  # Invalid character
            "test<>.{ext}",  # Invalid characters
            "{domain}/*.{ext}",  # Invalid character
            "{path}|{ext}",  # Invalid character
        ]
        for template in invalid_templates:
            with self.assertRaises(ValueError):
                FilenameTemplate(template)

    def test_directory_structure_preserved(self):
        """Test that directory structure is preserved using path_dirs variable."""
        template = FilenameTemplate("{domain}/{path_dirs}.{ext}")
        test_cases = [
            ("https://example.com/path/to/file", "example.com/path/to/file.txt"),
            ("https://example.com/dir/subdir/page", "example.com/dir/subdir/page.txt"),
            ("https://example.com/a/b/c/d", "example.com/a/b/c/d.txt"),
        ]
        for url, expected in test_cases:
            output_dir, _ = template.generate("content", url=url)
            self.assertEqual(
                output_dir, expected, f"Failed directory structure for URL: {url}"
            )

    def test_directory_structure_with_url(self):
        """Test directory structure generation with URL components using path_dirs."""
        content = "test content"
        template = FilenameTemplate("{domain}/{path_dirs}.{ext}")
        url = "https://example.com/path/to/page"
        output_dir, destination_dir = template.generate(content, url=url)

        expected_output_dir = os.path.join("example.com", "path/to")
        expected_path = os.path.join(expected_output_dir, "page.txt")

        self.assertEqual(destination_dir, expected_output_dir)
        self.assertEqual(output_dir, expected_path)

    def test_flattened_structure_with_url(self):
        """Test flattened directory structure with URL components using path variable."""
        content = "test content"
        template = FilenameTemplate("{domain}/{path}.{ext}")
        url = "https://example.com/path/to/page"
        output_dir, destination_dir = template.generate(content, url=url)

        expected_path = "example.com"
        expected_dir = os.path.join(expected_path, "path_to_page.txt")

        self.assertEqual(output_dir, expected_dir)
        self.assertEqual(destination_dir, expected_path)

    def test_basic_hash_template(self):
        """Test basic hash-based template."""
        content = "test content"
        template = FilenameTemplate("{hash}.{ext}")
        output_dir, destination_dir = template.generate(content)

        self.assertEqual(output_dir, "")
        self.assertTrue(destination_dir.endswith(".txt"))
        self.assertIn(generate_hash_filename(content), destination_dir)

    def test_custom_output_directory(self):
        """Test with custom output directory."""
        content = "test content"
        template = FilenameTemplate("{hash}.{ext}", output_dir="/custom/output")
        output_path, destination_dir = template.generate(content)

        self.assertEqual(destination_dir, "/custom/output")
        self.assertTrue(output_path.startswith("/custom/output/"))
        self.assertTrue(output_path.endswith(".txt"))

    def test_url_parameters(self):
        """Test handling of URL parameters."""
        content = "test content"
        template = FilenameTemplate("{domain}/{path}/{params}.{ext}")
        url = "https://example.com/page?param1=value1&param2=value2"
        output_dir, destination_dir = template.generate(content, url=url)

        expected_dir = os.path.join("example.com", "page")
        self.assertEqual(destination_dir, expected_dir)
        self.assertTrue("param1-value1_param2-value2" in output_dir)

    def test_sanitization(self):
        """Test path sanitization."""
        content = "test content"
        template = FilenameTemplate("{domain}/{path}.{ext}")
        url = "https://example.com/path/with spaces/and<>special:chars"
        output_dir, _ = template.generate(content, url=url)

        self.assertNotIn(" ", output_dir)
        self.assertNotIn("<", output_dir)
        self.assertNotIn(">", output_dir)
        self.assertNotIn(":", output_dir)
        self.assertTrue(output_dir.endswith(".txt"))

    def test_dot_segments(self):
        """Test handling of dot and dot-dot segments."""
        content = "test content"
        template = FilenameTemplate("{domain}/{path_dirs}.{ext}")
        url = "https://example.com/./path/../to/./page"
        output_dir, _ = template.generate(content, url=url)

        self.assertIn("_d_", output_dir)  # . becomes _d_
        self.assertIn("_dd_", output_dir)  # .. becomes _dd_

    def test_missing_url(self):
        """Test behavior when URL is missing but required."""
        content = "test content"
        template = FilenameTemplate("{domain}/{path}.{ext}")

        with self.assertRaises(ValueError):
            template.generate(content)

    def test_empty_content_handling(self):
        """Test empty content handling across different template scenarios."""
        test_cases = [
            # Basic template
            {
                "template": "{hash}.{ext}",
                "url": None,
                "filename": None,
                "output_dir": "",
                "destination_dir": "uOHdo6wKo4IK0pkL.txt",
                "content": "",
            },
            # Template with URL components
            {
                "template": "{domain}/{path}/{hash}.{ext}",
                "url": "https://example.com/test",
                "filename": None,
                "output_dir": "example.com/test/uOHdo6wKo4IK0pkL.txt",
                "destination_dir": "example.com/test",
                "content": "",
            },
            # Template with filename components
            {
                "template": "{file_basepath}/{file_basename}_{hash}.{ext}",
                "url": None,
                "filename": "dir/test.txt",
                "output_dir": "dir/test_uOHdo6wKo4IK0pkL.txt",
                "destination_dir": "dir",
                "content": "",
            },
            # Complex template with all components
            {
                "template": "{domain}/{path_dirs}/{file_basename}_{hash}.{ext}",
                "url": "https://example.com/path/to/file",
                "filename": "local/doc.txt",
                "output_dir": "example.com/path/to/file/doc_uOHdo6wKo4IK0pkL.txt",
                "destination_dir": "example.com/path/to/file",
                "content": "",
            },
        ]

        for case in test_cases:
            template = FilenameTemplate(case["template"])
            output_dir, destination_dir = template.generate(
                case["content"], url=case["url"], filename=case["filename"]
            )

            # Validate output dir
            self.assertEqual(output_dir, case["output_dir"])

            # Validate full path
            self.assertEqual(destination_dir, case["destination_dir"])

            # Validate path is valid and normalized
            self.assertTrue(os.path.normpath(destination_dir))

            # Check for no double separators
            self.assertNotIn("//", destination_dir)
            self.assertNotIn("\\\\", destination_dir)

    def test_custom_extension(self):
        """Test custom file extension."""
        content = "test content"
        template = FilenameTemplate("{hash}.{ext}", ext="json")
        _, destination_dir = template.generate(content)

        self.assertTrue(destination_dir.endswith(".json"))

    def test_path_length_limits(self):
        """Test path length limiting."""
        content = "test content"
        long_path = "a" * 300
        url = f"https://example.com/{long_path}"

        template = FilenameTemplate("{domain}/{path}.{ext}", max_length=50)
        output_dir, _ = template.generate(content, url=url)

        self.assertLessEqual(
            len(output_dir),
            50,
            f"Generated path length {len(output_dir)} exceeds limit of 50: {output_dir}",
        )
        self.assertTrue(output_dir.endswith(".txt"))

    def test_minimal_truncation(self):
        """Test truncation with minimal possible length."""
        url = "https://example.com/"
        content = "test content"
        template = FilenameTemplate("{domain}/{hash}.{ext}", max_length=21)
        output_dir, _ = template.generate(content, url=url)

        # Hash length (16) + ".txt" (4) + truncation flag "_ttt_" (5)
        self.assertEqual(
            output_dir,
            "_ttt_eA2ZYxECccrTXcoP.txt",
            f"Path does not match: {output_dir}",
        )
        self.assertLessEqual(
            len(output_dir), 25, f"Length not match for path: {output_dir}"
        )
        self.assertIn(
            generate_hash_filename(content), f"Hash not found in path: {output_dir}"
        )

    def test_truncation_with_preserved_dirs(self):
        """Test path truncation while preserving directory structure."""
        content = "test content"
        template = FilenameTemplate("{domain}/{path_dirs}.{ext}", max_length=50)

        long_segments = "/".join(["segment" + str(i) for i in range(10)])
        url = f"https://example.com/{long_segments}"
        output_dir, _ = template.generate(content, url=url)

        self.assertLessEqual(
            len(output_dir),
            50,
            f"Generated path length {len(output_dir)} exceeds limit of 50: {output_dir}",
        )
        self.assertTrue(
            output_dir.startswith("example.com"),
            f"Path does not start with domain: {output_dir}",
        )
        self.assertIn(
            "_ttt_", output_dir, f"Truncation indicator not found in path: {output_dir}"
        )
        self.assertTrue(output_dir.endswith(".txt"))
        self.assertIn(generate_hash_filename(content), output_dir)

    def test_truncation_without_dirs(self):
        """Test path truncation with flattened directory structure."""
        content = "test content"
        template = FilenameTemplate("{domain}/{path}.{ext}", max_length=40)

        url = "https://example.com/" + "a" * 100
        output_dir, _ = template.generate(content, url=url)

        self.assertLessEqual(
            len(output_dir),
            40,
            f"Generated path length {len(output_dir)} exceeds limit of 40: {output_dir}",
        )
        self.assertTrue(
            output_dir.startswith("example.com"),
            f"Path does not start with domain: {output_dir}",
        )
        self.assertIn(
            "_ttt_", output_dir, f"Truncation indicator not found in path: {output_dir}"
        )
        self.assertTrue(output_dir.endswith(".txt"))
        self.assertIn(generate_hash_filename(content), output_dir)

    def test_truncation_preserves_important_parts(self):
        """Test that truncation preserves essential path components while meeting length limits."""
        content = "test content"
        template = FilenameTemplate("{domain}/{path_dirs}/{hash}.{ext}", max_length=50)

        # Test URL with important segments
        url = "https://example.com/category/important-section/article"
        output_dir, _ = template.generate(content, url=url)

        # Basic assertions
        self.assertTrue(
            output_dir.startswith("example.com"), f"Domain not preserved: {output_dir}"
        )
        self.assertIn(
            "category", output_dir, f"Important path segment missing: {output_dir}"
        )
        self.assertIn(
            "_ttt_", output_dir, f"Truncation indicator missing: {output_dir}"
        )

        # Verify hash is preserved
        content_hash = generate_hash_filename(content)
        self.assertIn(content_hash, output_dir, f"Content hash missing: {output_dir}")

        # Length constraint
        self.assertLessEqual(
            len(output_dir), 50, f"Path exceeds length limit: {output_dir}"
        )

        # Directory structure assertions
        dir_parts = output_dir.split(os.sep)
        self.assertEqual(
            dir_parts[0], "example.com", "Domain not preserved in directory structure"
        )
        self.assertEqual(
            dir_parts[1], "category", "Category not preserved in directory structure"
        )

        # Test with very long path components
        long_url = "https://example.com/" + "/".join(
            ["segment" + str(i) for i in range(10)]
        )
        output_dir2, _ = template.generate(content, url=long_url)

        # Verify long path handling
        self.assertLessEqual(len(output_dir2), 50, "Long path not properly truncated")
        self.assertTrue(
            output_dir2.startswith("example.com"), "Domain lost in long path truncation"
        )
        self.assertIn("_ttt_", output_dir2, "Truncation indicator missing in long path")
        self.assertIn(content_hash, output_dir2, "Hash missing in long path")
        self.assertTrue(output_dir2.endswith(".txt"), "Extension missing in long path")

    def test_truncation_with_custom_output_dir(self):
        """Test truncation behavior with custom output directory."""
        content = "test content"
        template = FilenameTemplate(
            "{domain}/{path_dirs}.{ext}", max_length=60, output_dir="/custom/output"
        )

        url = "https://example.com/very/long/path/that/needs/truncation"
        output_dir, _ = template.generate(content, url=url)

        self.assertTrue(
            output_dir.startswith("/custom/output"),
            f"Output directory missing from path: {output_dir}",
        )
        self.assertLessEqual(
            len(output_dir),
            60,
            f"Generated path length {len(output_dir)} exceeds limit of 60: {output_dir}",
        )
        self.assertIn(
            "_ttt_", output_dir, f"Truncation indicator not found in path: {output_dir}"
        )
        self.assertTrue(output_dir.endswith(".txt"))


if __name__ == "__main__":
    unittest.main()
