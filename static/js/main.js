document.addEventListener('DOMContentLoaded', function() {
    // 手机端侧边抽屉菜单
    const mobileAvatarBtn = document.getElementById('mobileAvatarBtn');
    const mobileDrawer = document.getElementById('mobileDrawer');
    const drawerBackdrop = document.getElementById('drawerBackdrop');
    const closeDrawerBtn = document.getElementById('closeDrawerBtn');

    if (mobileAvatarBtn && mobileDrawer && drawerBackdrop) {
        function openDrawer() {
            mobileDrawer.classList.add('active');
            drawerBackdrop.classList.add('active');
            document.body.style.overflow = 'hidden'; // 阻止背景滚动
        }

        function closeDrawer() {
            mobileDrawer.classList.remove('active');
            drawerBackdrop.classList.remove('active');
            document.body.style.overflow = '';
        }

        mobileAvatarBtn.addEventListener('click', openDrawer);
        drawerBackdrop.addEventListener('click', closeDrawer);
        if (closeDrawerBtn) {
            closeDrawerBtn.addEventListener('click', closeDrawer);
        }
    }

    // 交互微动画与状态模拟
    // 转发模拟（后端转发留给后续任务）
    const repostButtons = document.querySelectorAll('.action-repost');
    repostButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const icon = this.querySelector('i');
            const countSpan = this.querySelector('.repost-count');
            let count = parseInt(countSpan.textContent) || 0;
            
            if (this.classList.contains('reposted')) {
                this.classList.remove('reposted');
                icon.className = 'bi bi-arrow-repeat';
                countSpan.textContent = count - 1 > 0 ? count - 1 : '';
            } else {
                this.classList.add('reposted');
                icon.className = 'bi bi-arrow-repeat text-success fw-bold';
                countSpan.textContent = count + 1;
            }
        });
    });

    // 评论模态框或发帖模态框触发器
    // 主要是悬浮 + 按钮拉起 Bootstrap 发帖 modal
    const mobileFab = document.getElementById('mobileFab');
    if (mobileFab) {
        mobileFab.addEventListener('click', function() {
            const postModalEl = document.getElementById('postModal');
            if (postModalEl) {
                const postModal = new bootstrap.Modal(postModalEl);
                postModal.show();
            }
        });
    }

    // ==================== 发帖图片选择与本地预览逻辑 ====================
    // 初始化单个发帖表单的联动逻辑
    function initPostFormLogic(config) {
        const form = document.getElementById(config.formId);
        const textarea = document.getElementById(config.textareaId);
        const fileInput = document.getElementById(config.fileInputId);
        const mediaBtn = document.getElementById(config.mediaBtnId);
        const previewWrapper = document.getElementById(config.previewWrapperId);
        const previewGrid = document.getElementById(config.previewGridId);
        const clearBtn = document.getElementById(config.clearBtnId);
        const submitBtn = document.getElementById(config.submitBtnId);
        const maxFiles = config.maxFiles || 4;

        if (!form || !textarea || !fileInput || !submitBtn) return;

        // 辅助：根据文字和图片更新按钮状态
        function updateButton() {
            const hasText = textarea.value.trim().length > 0;
            const hasImage = fileInput.files && fileInput.files.length > 0;
            submitBtn.disabled = (!hasText && !hasImage);
        }

        // 1. 点击媒体图标触发文件选择
        if (mediaBtn) {
            mediaBtn.addEventListener('click', () => fileInput.click());
        }

        function selectedFiles() {
            return Array.from(fileInput.files || []);
        }

        function applyFileLimit() {
            const files = selectedFiles();
            if (files.length <= maxFiles) {
                return files;
            }

            const dataTransfer = new DataTransfer();
            files.slice(0, maxFiles).forEach(file => dataTransfer.items.add(file));
            fileInput.files = dataTransfer.files;
            alert(`You can upload up to ${maxFiles} images per post.`);
            return selectedFiles();
        }

        function renderPreview(files) {
            if (!previewGrid || !previewWrapper) return;

            previewGrid.innerHTML = '';
            previewGrid.className = `post-image-preview-grid post-image-preview-count-${files.length}`;

            files.forEach((file, index) => {
                const itemDiv = document.createElement('div');
                itemDiv.className = 'preview-image-item';

                const img = document.createElement('img');
                img.src = URL.createObjectURL(file);
                img.alt = file.name;
                img.onload = () => URL.revokeObjectURL(img.src);
                itemDiv.appendChild(img);

                // 创建单独的 X 删除按钮
                const deleteBtn = document.createElement('button');
                deleteBtn.type = 'button';
                deleteBtn.className = 'preview-image-delete-btn';
                deleteBtn.innerHTML = '<i class="bi bi-x fs-6"></i>';
                
                // 绑定点击事件排除对应的文件
                deleteBtn.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    removeSingleFile(index);
                });

                itemDiv.appendChild(deleteBtn);
                previewGrid.appendChild(itemDiv);
            });

            previewWrapper.classList.toggle('d-none', files.length === 0);
        }

        // 精准移出被删去的文件
        function removeSingleFile(indexToRemove) {
            const currentFiles = selectedFiles();
            const dataTransfer = new DataTransfer();

            currentFiles.forEach((file, idx) => {
                if (idx !== indexToRemove) {
                    dataTransfer.items.add(file);
                }
            });

            fileInput.files = dataTransfer.files;
            
            // 刷新
            const updatedFiles = selectedFiles();
            renderPreview(updatedFiles);
            updateButton();
        }

        // 2. 选择文件后的本地读取预览
        fileInput.addEventListener('change', function() {
            const files = applyFileLimit();
            renderPreview(files);
            updateButton();
        });

        // 3. 清除选中图片
        function clearImages() {
            fileInput.value = '';
            if (previewWrapper) {
                previewWrapper.classList.add('d-none');
            }
            if (previewGrid) {
                previewGrid.innerHTML = '';
                previewGrid.className = 'post-image-preview-grid';
            }
            updateButton();
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', clearImages);
        }

        // 4. 输入文字的监听
        textarea.addEventListener('input', updateButton);

        // 初始状态计算
        updateButton();
    }

    // 运行 PC 端发帖联动
    initPostFormLogic({
        formId: 'pc-post-form',
        textareaId: 'pc-post-textarea',
        fileInputId: 'pc-post-image-input',
        mediaBtnId: 'pc-media-btn',
        previewWrapperId: 'pc-image-preview-wrapper',
        previewGridId: 'pc-image-preview-grid',
        clearBtnId: null,
        submitBtnId: 'pc-post-submit',
        maxFiles: 4
    });

    // 运行 Modal 弹窗发帖联动
    initPostFormLogic({
        formId: 'modal-post-form',
        textareaId: 'modal-post-textarea',
        fileInputId: 'modal-post-image',
        mediaBtnId: null, // label for 属性已绑定触发 file select，无需 JS 点击
        previewWrapperId: 'modal-image-preview-wrapper',
        previewGridId: 'modal-image-preview-grid',
        clearBtnId: null,
        submitBtnId: 'modal-post-submit',
        maxFiles: 4
    });

    // ==================== 全屏大图 Lightbox 灯箱逻辑 ====================
    const lightbox = document.getElementById('globalLightbox');
    const lightboxImg = document.getElementById('lightboxImage');

    if (lightbox && lightboxImg) {
        // 打开灯箱
        window.openLightbox = function(src) {
            lightboxImg.src = src;
            lightbox.classList.remove('d-none');
            document.body.style.overflow = 'hidden'; // 锁定网页滚动
            
            // 延迟以启动 CSS opacity/scale 动画
            setTimeout(() => {
                lightbox.classList.add('active');
            }, 10);
        };

        // 关闭灯箱
        window.closeLightbox = function() {
            lightbox.classList.remove('active');
            
            // 动画结束后隐藏 DOM
            setTimeout(() => {
                lightbox.classList.add('d-none');
                lightboxImg.src = '';
                document.body.style.overflow = ''; // 还原滚动
            }, 250);
        };

        // 1. 使用高效的【事件委托】机制监听 timeline 或 profile 卡片里的图片点击
        document.body.addEventListener('click', function(e) {
            // 只有当点击图片且它属于 post-card-media 组件时触发
            if (e.target.tagName === 'IMG' && e.target.closest('.post-card-media')) {
                e.preventDefault();
                window.openLightbox(e.target.src);
            }
        });

        // 2. 支持 Esc 键关闭
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && !lightbox.classList.contains('d-none')) {
                window.closeLightbox();
            }
        });
    }
});
